"""
Wiring Validator - GPU-Aware Cabling Verification for AI Clusters

This module validates physical cabling against logical topology expectations
using LLDP (Link Layer Discovery Protocol) neighbor data from switches.

**The Critical Problem:**
In a 4K GPU cluster with 32,768 cables, a single mis-wire causes:
- ❌ 15-40% degradation in All-Reduce collective operations
- ❌ Cross-plane traffic (defeats InfiniBrand rail isolation)
- ❌ Cross-SU traffic (suboptimal routing across Scalable Units)
- ❌ Unpredictable latency (some GPUs are N+1 hops away)
- ❌ Discovered only during Day 2 training runs ($50K+ delay cost)

**The Solution:**
Post-provisioning wiring audit using LLDP neighbor discovery:
1. Switch reports what it **actually** sees on each port (LLDP)
2. We compare against what GPU **should** be there (GPUToLeafMapper)
3. Validate Rail Isolation (Plane 0 must only see Plane 0)
4. Validate SU Isolation (SU-1 must only see SU-1)
5. Generate actionable "fix-it" alerts for Installation Lead

**Workflow:**
```
Switch boots → Executes ZTP → LLDP enabled → Collects neighbors
    ↓
POST /validate-cabling with neighbor list
    ↓
WiringValidator compares Expected vs Actual
    ↓
Generate health report + create alerts for mis-wires
    ↓
Dashboard shows color-coded rack with swap instructions
```

Example:
    validator = WiringValidator(topology, mapper)
    expected = validator.generate_expected_neighbors(plane_id=0, leaf_id=1)
    # → {"p1": "B200-Rack01-Srv01-GPU1-HCA0", ...}
    
    report = validator.validate_cabling(
        switch_id="IB-LEAF-P0-L01",
        plane_id=0,
        leaf_id=1,
        actual_neighbors=[...]
    )
    # → {"cluster_healthy": False, "failed": 2, "results": [...]}
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from app.libs.cluster_topology import ClusterTopology
from app.libs.gpu_to_leaf_mapper import GPUToLeafMapper
from app.libs.multi_su_test_suite import SUIDExtractor, MultiSUValidator
import re


# ============================================================================
# HOSTNAME PARSING UTILITIES
# ============================================================================

def extract_tail_from_hostname(hostname: str) -> int:
    """Extract tail/plane ID from GPU HCA hostname with robust pattern matching.
    
    **The Challenge:**
    Real-world LLDP neighbor hostnames are often "noisy" due to:
    - FQDN suffixes: "B200-R01-S05-GPU3-Tail0.mellanox.com"
    - Management prefixes: "eth0.B200-R01-S05-GPU3-Tail0"
    - Truncation: "node-14-hca-1" (legacy naming)
    - Unknown devices: "Unknown-Device-123" (firmware issues)
    
    **Why This Matters:**
    In 8-rail GPU clusters, every InfiniBand plane must maintain strict
    isolation. A single Tail-1 cable on a Plane-0 switch causes:
    - ❌ 15-40% All-Reduce degradation
    - ❌ Non-deterministic routing across rails
    - ❌ GPUDirect RDMA failures during training
    
    **Parsing Strategy:**
    1. Primary: Match "Tail-N" or "Tail N" (NVIDIA standard)
    2. Fallback 1: Match "HCA-N" or "HCA N" (alternate naming)
    3. Fallback 2: Match "hca-N" or "hcaN" (legacy lowercase)
    4. Return -1: Unknown format (flags manual triage)
    
    Args:
        hostname: LLDP neighbor hostname from switch neighbor table
        
    Returns:
        Integer tail ID (0-7 for 8-rail) or -1 if parsing failed
        
    Examples:
        >>> extract_tail_from_hostname("B200-R01-S05-GPU3-Tail0")
        0
        
        >>> extract_tail_from_hostname("eth0.B200-R01-S05-GPU3-Tail1.mellanox.com")
        1
        
        >>> extract_tail_from_hostname("node-14-hca-2")
        2
        
        >>> extract_tail_from_hostname("Unknown-Device-123")
        -1  # Flags for manual investigation
    
    **Critical for Rail Isolation:**
    This parser is the first line of defense against cross-plane cabling.
    A return value of -1 should trigger a CRITICAL alert because:
    - Device might have uninitialized HCA driver
    - Firmware mismatch preventing proper LLDP reporting
    - Both scenarios will also kill training performance
    """
    if not hostname:
        return -1
    
    # Pattern 1: "Tail-N" or "Tail N" (NVIDIA standard)
    # Handles: "B200-R01-S12-GPU1-Tail0", "GPU3-Tail 1"
    match = re.search(r'Tail[-\s]?(\d+)', hostname, re.IGNORECASE)
    if match:
        tail_id = int(match.group(1))
        print(f"   ✅ Extracted Tail {tail_id} from: {hostname}")
        return tail_id
    
    # Pattern 2: "HCA-N" or "HCA N" (alternate naming)
    # Handles: "Server-Rack01-S05-GPU3-HCA-2", "node-hca 1"
    match = re.search(r'HCA[-\s]?(\d+)', hostname, re.IGNORECASE)
    if match:
        tail_id = int(match.group(1))
        print(f"   ✅ Extracted Tail {tail_id} (via HCA) from: {hostname}")
        return tail_id
    
    # Pattern 3: "hcaN" (legacy lowercase, no separator)
    # Handles: "node-14-hca1", "gpu-hca2"
    match = re.search(r'hca(\d+)', hostname, re.IGNORECASE)
    if match:
        tail_id = int(match.group(1))
        print(f"   ⚠️ Extracted Tail {tail_id} (legacy format) from: {hostname}")
        return tail_id
    
    # No match found - unknown/malformed hostname
    print(f"   ❌ UNKNOWN TAIL ID: Could not parse '{hostname}'")
    print("      → This device may have uninitialized HCA driver or firmware mismatch")
    return -1


@dataclass
class LLDPNeighborInfo:
    """LLDP neighbor information from switch."""
    port_id: str              # "Ethernet1/1", "p1", "et-0/0/1"
    neighbor_hostname: str    # "B200-Rack01-Srv03-GPU2-HCA0"
    neighbor_description: Optional[str] = None
    neighbor_mac: Optional[str] = None


@dataclass
class PortValidationResult:
    """Validation result for a single port."""
    port_id: str
    port_number: int  # Normalized port number (1-based)
    status: str  # "PASS", "FAIL", "MISSING"
    expected_neighbor: Optional[str]
    actual_neighbor: Optional[str]
    mismatch_details: Optional[str] = None
    swap_recommendation: Optional[str] = None


@dataclass
class CablingValidationReport:
    """Complete cabling validation report for a switch."""
    switch_id: str
    plane_id: int
    leaf_id: int
    cluster_healthy: bool
    total_ports: int
    passed: int
    failed: int
    missing: int
    health_percentage: float
    results: List[PortValidationResult]
    swap_recommendations: List[str]


class WiringValidator:
    """Validates physical cabling against GPU-aware topology expectations.
    
    The WiringValidator is the "Traffic Court" for cabling errors. It compares
    what switches **actually** see via LLDP against what they **should** see
    based on the ClusterTopology and GPUToLeafMapper.
    
    **Key Responsibilities:**
    1. Generate expected neighbor matrix for each leaf switch
    2. Compare actual LLDP neighbors against expectations
    3. Detect mis-wires with fuzzy hostname matching
    4. Generate swap recommendations for symmetric errors
    5. Calculate cluster health percentage
    
    **Why This Matters:**
    Without this validation, you might have 1,000 servers that "look" online,
    but All-Reduce operations are 40% slower because a few GPUs are crossing
    planes or rails. This validator ensures:
    - ✅ Latency Consistency: Every GPU is exactly N hops away
    - ✅ Rail Isolation: No cable bridges Plane 0 and Plane 1
    - ✅ Technician Accountability: Clear fix-it lists
    """
    
    def __init__(self, topology: ClusterTopology, mapper: GPUToLeafMapper):
        """Initialize validator with topology and GPU-to-Leaf mapper.
        
        Args:
            topology: ClusterTopology instance defining network geometry
            mapper: GPUToLeafMapper for GPU-to-switch port mapping
        """
        self.topology = topology
        self.mapper = mapper
        
        print("🔍 WiringValidator initialized")
        print(f"   Topology: {topology.total_gpus} GPUs, {topology.total_leafs} leafs")
    
    def generate_expected_neighbors(
        self, 
        plane_id: int, 
        leaf_id: int
    ) -> Dict[int, str]:
        """Generate expected neighbor matrix for a specific leaf switch.
        
        Uses GPUToLeafMapper to determine which GPU should be connected
        to each port on this leaf, then formats as expected hostname.
        
        Args:
            plane_id: Plane ID (0-indexed)
            leaf_id: Leaf ID within plane (0-indexed)
            
        Returns:
            Dict mapping port_number (int) → expected_gpu_hostname (str)
            Example: {1: "B200-Rack01-Srv01-GPU1-HCA0", ...}
            
        Example:
            >>> validator.generate_expected_neighbors(plane_id=0, leaf_id=1)
            {
                1: "B200-Rack01-Srv01-GPU1-HCA0",
                2: "B200-Rack01-Srv02-GPU1-HCA0",
                ...
            }
        """
        print(f"\n📋 Generating expected neighbors for Plane {plane_id}, Leaf {leaf_id}")
        
        # Get port mapping from GPUToLeafMapper
        port_mapping = self.mapper.get_port_mapping_for_leaf(plane_id, leaf_id)
        
        expected_neighbors = {}
        
        for port_num, gpu_info in port_mapping.items():
            rack = gpu_info['rack']
            server = gpu_info['server']
            gpu = gpu_info['gpu']
            tail = gpu_info['tail']
            
            # Format expected hostname
            expected_hostname = self._format_gpu_hostname(
                rack=rack,
                server=server,
                gpu=gpu,
                tail=tail
            )
            
            expected_neighbors[port_num] = expected_hostname
        
        print(f"   Generated {len(expected_neighbors)} expected neighbors")
        return expected_neighbors
    
    def validate_cabling(
        self,
        switch_id: str,
        plane_id: int,
        leaf_id: int,
        actual_neighbors: List[LLDPNeighborInfo]
    ) -> CablingValidationReport:
        """Validate actual LLDP neighbors against expected topology.
        
        This is the main validation entry point. Compares what the switch
        actually sees (via LLDP) against what it should see (via topology).
        
        Args:
            switch_id: Switch identifier (e.g., "IB-LEAF-P0-L01")
            plane_id: Plane ID (0-indexed)
            leaf_id: Leaf ID within plane (0-indexed)
            actual_neighbors: List of LLDP neighbor data from switch
            
        Returns:
            CablingValidationReport with per-port validation results
            
        Example:
            >>> report = validator.validate_cabling(
            ...     switch_id="IB-LEAF-P0-L01",
            ...     plane_id=0,
            ...     leaf_id=1,
            ...     actual_neighbors=[
            ...         LLDPNeighborInfo(port_id="p1", neighbor_hostname="B200-R01-S01-GPU1-HCA0"),
            ...         LLDPNeighborInfo(port_id="p2", neighbor_hostname="B200-R01-S02-GPU1-HCA0"),
            ...     ]
            ... )
            >>> report.cluster_healthy
            True
        """
        print(f"\n{'='*70}")
        print(f"🔍 CABLING VALIDATION: {switch_id}")
        print(f"   Plane: {plane_id}, Leaf: {leaf_id}")
        print(f"   Received {len(actual_neighbors)} LLDP neighbors")
        print(f"{'='*70}")
        
        # Generate expected neighbors for this leaf
        expected_neighbors = self.generate_expected_neighbors(plane_id, leaf_id)
        
        # Create lookup: port_number → actual neighbor
        actual_by_port = {}
        for neighbor in actual_neighbors:
            port_num = self._normalize_port_id(neighbor.port_id)
            if port_num:
                actual_by_port[port_num] = neighbor
        
        # Validate each expected port
        results = []
        passed = 0
        failed = 0
        missing = 0
        
        for port_num, expected_hostname in expected_neighbors.items():
            actual_neighbor = actual_by_port.get(port_num)
            
            if not actual_neighbor:
                # Port expected but no LLDP neighbor detected
                result = PortValidationResult(
                    port_id=f"p{port_num}",
                    port_number=port_num,
                    status="MISSING",
                    expected_neighbor=expected_hostname,
                    actual_neighbor=None,
                    mismatch_details="No LLDP neighbor detected (cable unplugged or device offline?)"
                )
                missing += 1
            else:
                # Compare expected vs actual
                is_match, mismatch_details = self._match_neighbor(
                    expected_hostname,
                    actual_neighbor.neighbor_hostname
                )
                
                if is_match:
                    result = PortValidationResult(
                        port_id=actual_neighbor.port_id,
                        port_number=port_num,
                        status="PASS",
                        expected_neighbor=expected_hostname,
                        actual_neighbor=actual_neighbor.neighbor_hostname
                    )
                    passed += 1
                else:
                    result = PortValidationResult(
                        port_id=actual_neighbor.port_id,
                        port_number=port_num,
                        status="FAIL",
                        expected_neighbor=expected_hostname,
                        actual_neighbor=actual_neighbor.neighbor_hostname,
                        mismatch_details=mismatch_details
                    )
                    failed += 1
            
            results.append(result)
        
        # Check for unexpected neighbors (ports reporting but not in expected list)
        for port_num, neighbor in actual_by_port.items():
            if port_num not in expected_neighbors:
                result = PortValidationResult(
                    port_id=neighbor.port_id,
                    port_number=port_num,
                    status="FAIL",
                    expected_neighbor=None,
                    actual_neighbor=neighbor.neighbor_hostname,
                    mismatch_details="Unexpected neighbor (port not in topology or wrong VLAN?)"
                )
                results.append(result)
                failed += 1
        
        # Calculate health metrics
        total_ports = len(expected_neighbors)
        cluster_healthy = (failed == 0 and missing == 0)
        health_percentage = (passed / total_ports * 100) if total_ports > 0 else 0
        
        # Generate swap recommendations
        swap_recommendations = self._generate_swap_recommendations(results)
        
        # Print summary
        print("\n📊 VALIDATION SUMMARY:")
        print(f"   Total Ports: {total_ports}")
        print(f"   ✅ Passed: {passed}")
        print(f"   ❌ Failed: {failed}")
        print(f"   ⚠️  Missing: {missing}")
        print(f"   Health: {health_percentage:.1f}%")
        print(f"   Status: {'🟢 HEALTHY' if cluster_healthy else '🔴 WIRING ERRORS'}")
        
        if swap_recommendations:
            print("\n💡 SWAP RECOMMENDATIONS:")
            for rec in swap_recommendations:
                print(f"   {rec}")
        
        return CablingValidationReport(
            switch_id=switch_id,
            plane_id=plane_id,
            leaf_id=leaf_id,
            cluster_healthy=cluster_healthy,
            total_ports=total_ports,
            passed=passed,
            failed=failed,
            missing=missing,
            health_percentage=health_percentage,
            results=results,
            swap_recommendations=swap_recommendations
        )
    
    def validate_rail_isolation(
        self,
        switch_id: str,
        plane_id: int,
        actual_neighbors: List[LLDPNeighborInfo]
    ) -> List[Dict[str, Any]]:
        """Validate rail isolation by ensuring all neighbors match the switch's plane.
        
        **The Critical Problem:**
        In 8-rail GPU clusters, each InfiniBand plane MUST maintain strict isolation.
        A single Tail-1 cable on a Plane-0 switch causes:
        - ❌ 15-40% All-Reduce degradation
        - ❌ Non-deterministic routing across rails  
        - ❌ GPUDirect RDMA failures during training
        - ❌ Discovered during $50K+ production runs (too late!)
        
        **Zero-Tolerance Policy:**
        Even ONE rail violation should flip the entire rack status to CRITICAL.
        In an All-Reduce collective, speed is limited by the slowest/most congested link.
        One crossed cable can throttle the throughput of 3,999 other GPUs.
        
        **Validation Logic:**
        1. Extract tail ID from each neighbor's hostname
        2. Compare tail ID to switch's plane_id
        3. If mismatch → CRITICAL violation
        4. If unparseable (tail=-1) → CRITICAL unknown device
        
        Args:
            switch_id: Switch identifier (e.g., "IB-LEAF-P0-L01")
            plane_id: Expected plane ID for this switch (0-7)
            actual_neighbors: List of LLDP neighbors detected by switch
            
        Returns:
            List of violations with structure:
            [
                {
                    'port_id': 'p17',
                    'expected_plane': 0,
                    'actual_tail': 1,
                    'neighbor_hostname': 'B200-R04-S12-GPU3-Tail1',
                    'severity': 'CRITICAL',
                    'impact': 'Cross-plane traffic degrades All-Reduce by 15-40%'
                }
            ]
            
        Example:
            >>> violations = validator.validate_rail_isolation(
            ...     switch_id="IB-LEAF-P0-L01",
            ...     plane_id=0,
            ...     actual_neighbors=[...]
            ... )
            >>> if violations:
            ...     # Block stage gate release
            ...     create_critical_alert(violations)
        """
        print(f"\n{'='*70}")
        print(f"🚨 RAIL ISOLATION CHECK: {switch_id}")
        print(f"   Expected Plane: {plane_id}")
        print(f"   Checking {len(actual_neighbors)} neighbors for cross-plane contamination")
        print(f"{'='*70}")
        
        violations = []
        
        for neighbor in actual_neighbors:
            # Extract tail ID from hostname
            detected_tail = extract_tail_from_hostname(neighbor.neighbor_hostname)
            
            # Case 1: Unparseable hostname (CRITICAL - firmware/driver issue)
            if detected_tail == -1:
                violation = {
                    'port_id': neighbor.port_id,
                    'expected_plane': plane_id,
                    'actual_tail': None,
                    'neighbor_hostname': neighbor.neighbor_hostname,
                    'severity': 'CRITICAL',
                    'violation_type': 'UNKNOWN_TAIL',
                    'impact': 'Device has uninitialized HCA driver or firmware mismatch - will kill training performance',
                    'action': 'Manual investigation required: Check HCA driver initialization and firmware version'
                }
                violations.append(violation)
                print(f"   ❌ UNKNOWN TAIL on {neighbor.port_id}: {neighbor.neighbor_hostname}")
                continue
            
            # Case 2: Tail ID doesn't match plane ID (CRITICAL - cross-plane wiring)
            if detected_tail != plane_id:
                violation = {
                    'port_id': neighbor.port_id,
                    'expected_plane': plane_id,
                    'actual_tail': detected_tail,
                    'neighbor_hostname': neighbor.neighbor_hostname,
                    'severity': 'CRITICAL',
                    'violation_type': 'RAIL_CONTAMINATION',
                    'impact': f'Cross-plane traffic detected: Plane {plane_id} switch has Tail-{detected_tail} neighbor. This degrades All-Reduce by 15-40% and breaks GPUDirect RDMA.',
                    'action': f'🔄 IMMEDIATE ACTION: Swap cable from Plane-{plane_id} switch to Plane-{detected_tail} switch'
                }
                violations.append(violation)
                print(f"   🚨 RAIL CROSS-CONTAMINATION on {neighbor.port_id}:")
                print(f"      Expected: Plane {plane_id} (Tail-{plane_id})")
                print(f"      Detected: Tail-{detected_tail}")
                print(f"      Neighbor: {neighbor.neighbor_hostname}")
                print("      → Cable is plugged into WRONG PLANE switch!")
            else:
                # Tail matches plane - this is correct
                print(f"   ✅ {neighbor.port_id}: Tail-{detected_tail} matches Plane {plane_id}")
        
        # Print summary
        print("\n📊 RAIL ISOLATION SUMMARY:")
        if violations:
            print(f"   🚨 CRITICAL: {len(violations)} rail violation(s) detected")
            print("   ⚠️  STATUS: RAIL_CONTAMINATION - BLOCK COMPUTE RELEASE")
            print("\n   Violations by type:")
            rail_contamination = sum(1 for v in violations if v['violation_type'] == 'RAIL_CONTAMINATION')
            unknown_tails = sum(1 for v in violations if v['violation_type'] == 'UNKNOWN_TAIL')
            if rail_contamination > 0:
                print(f"      🔄 Cross-plane wiring: {rail_contamination}")
            if unknown_tails > 0:
                print(f"      ❓ Unknown tail IDs: {unknown_tails}")
        else:
            print(f"   ✅ All neighbors match Plane {plane_id} - Rail isolation INTACT")
        
        return violations
    
    def validate_su_boundary_enforcement(
        self,
        switch_id: str,
        actual_neighbors: List[LLDPNeighborInfo]
    ) -> List[Dict[str, Any]]:
        """Validate SU boundary enforcement - prevent cross-SU contamination.
        
        **The Critical Problem:**
        In multi-SU SuperPOD deployments (4K+ GPUs), each Scalable Unit operates
        as an isolated network domain. A single cable bridging SU-1 and SU-2 causes:
        - ❌ Suboptimal All-Reduce routing (hairpin paths through Tier 3)
        - ❌ 15-40% latency increase on affected GPUs
        - ❌ BGP routing instability if ASN ranges overlap
        - ❌ Nearly impossible to debug after cluster is in production
        
        **Zero-Tolerance Policy:**
        Cross-SU cabling is a STOP-SHIP event. Even one cable creates a "phantom bridge"
        that defeats the hierarchical fabric design. Installation Lead must fix before
        releasing the cluster for compute workloads.
        
        **Validation Logic:**
        1. Extract SU_ID from local switch hostname (e.g., "SU1-L3-P0" → SU_ID=1)
        2. Extract SU_ID from each neighbor hostname
        3. If local_su != neighbor_su → CRITICAL cross-SU violation
        4. Exception: Tier 3 Super-Spine switches (CORE-*) are allowed to cross SUs
        
        Args:
            switch_id: Switch identifier with SU prefix (e.g., "SU1-L3-P0")
            actual_neighbors: List of LLDP neighbors detected by switch
            
        Returns:
            List of cross-SU violations:
            [
                {
                    'port_id': 'p22',
                    'local_switch': 'SU1-L3-P0',
                    'neighbor_switch': 'SU2-S5-P0',
                    'local_su': 1,
                    'neighbor_su': 2,
                    'severity': 'CRITICAL',
                    'violation_type': 'CROSS_SU_CONTAMINATION',
                    'impact': 'All-Reduce traffic will take suboptimal path through Tier 3',
                    'action': 'Swap cable to correct SU immediately'
                }
            ]
        """
        print(f"\n{'='*70}")
        print(f"🚫 MULTI-SU BOUNDARY CHECK: {switch_id}")
        print(f"   Checking {len(actual_neighbors)} neighbors for cross-SU contamination")
        print(f"{'='*70}")
        
        # Extract SU_ID from local switch
        local_su = SUIDExtractor.extract_su_id(switch_id)
        
        if local_su is None:
            # Switch doesn't have SU prefix - might be legacy naming or Tier 3
            print(f"   ⚠️  Switch '{switch_id}' has no SU prefix - skipping SU validation")
            print("      (This is normal for Tier 3 Super-Spine switches)")
            return []
        
        print(f"   Local Switch SU_ID: {local_su}")
        
        violations = []
        
        for neighbor in actual_neighbors:
            # Validate this neighbor against local SU
            is_valid, violation_msg = MultiSUValidator.validate_cable_connection(
                local_hostname=switch_id,
                remote_hostname=neighbor.neighbor_hostname
            )
            
            if not is_valid:
                # Extract neighbor SU for detailed reporting
                neighbor_su = SUIDExtractor.extract_su_id(neighbor.neighbor_hostname)
                
                violation = {
                    'port_id': neighbor.port_id,
                    'local_switch': switch_id,
                    'neighbor_switch': neighbor.neighbor_hostname,
                    'local_su': local_su,
                    'neighbor_su': neighbor_su,
                    'severity': 'CRITICAL',
                    'violation_type': 'CROSS_SU_CONTAMINATION',
                    'impact': f'All-Reduce traffic from SU{local_su} will hairpin through Tier 3 to reach SU{neighbor_su}. This adds 2+ hops of latency and degrades performance by 15-40%.',
                    'action': f'🔄 IMMEDIATE ACTION: Disconnect {neighbor.port_id} and reconnect to a switch in SU{local_su}',
                    'details': violation_msg
                }
                violations.append(violation)
                
                print(f"   🚨 CROSS-SU CONTAMINATION on {neighbor.port_id}:")
                print(f"      Local: {switch_id} (SU{local_su})")
                print(f"      Neighbor: {neighbor.neighbor_hostname} (SU{neighbor_su})")
                print("      → Cable bridges TWO DIFFERENT SCALABLE UNITS!")
            else:
                # Same SU - this is correct
                neighbor_su = SUIDExtractor.extract_su_id(neighbor.neighbor_hostname)
                if neighbor_su is not None:
                    print(f"   ✅ {neighbor.port_id}: SU{neighbor_su} matches local SU{local_su}")
        
        # Print summary
        print("\n📊 SU BOUNDARY ENFORCEMENT SUMMARY:")
        if violations:
            print(f"   🚨 CRITICAL: {len(violations)} cross-SU violation(s) detected")
            print("   ⚠️  STATUS: CROSS_SU_CONTAMINATION - BLOCK COMPUTE RELEASE")
            print("\n   🔥 IMPACT: These cables create phantom bridges between isolated SUs")
            print("      All-Reduce operations will suffer severe performance degradation")
        else:
            print(f"   ✅ All neighbors within SU{local_su} - Boundary isolation INTACT")
        
        return violations
    
    def validate_dual_key_isolation(
        self,
        switch_id: str,
        plane_id: int,
        actual_neighbors: List[LLDPNeighborInfo]
    ) -> Dict[str, Any]:
        """Validate both Rail AND SU boundary isolation (Dual-Key Enforcement).
        
        This is the comprehensive validation method that enforces BOTH critical
        isolation boundaries in multi-SU GPU clusters:
        
        **Key 1: Rail Isolation (Plane Separation)**
        - Plane 0 switches must only see Tail-0 neighbors
        - Prevents cross-plane traffic
        
        **Key 2: SU Isolation (Scalable Unit Boundary)**
        - SU-1 switches must only see SU-1 neighbors
        - Prevents cross-SU traffic
        
        **Why Both Matter:**
        - Rail violations: 15-40% degradation from cross-plane contention
        - SU violations: 15-40% degradation from hairpin routing
        - Both together: Potential 50%+ performance loss (catastrophic)
        
        Args:
            switch_id: Switch identifier (e.g., "SU1-L3-P0")
            plane_id: Expected plane ID (0-indexed)
            actual_neighbors: List of LLDP neighbors from switch
            
        Returns:
            Comprehensive validation report:
            {
                'switch_id': 'SU1-L3-P0',
                'plane_id': 0,
                'su_id': 1,
                'status': 'CRITICAL',  # or 'PASS'
                'rail_violations': [...],
                'su_violations': [...],
                'total_violations': 3,
                'cluster_ready': False,
                'action_required': True
            }
        """
        print(f"\n{'#'*70}")
        print("# DUAL-KEY ISOLATION VALIDATION")
        print(f"# Switch: {switch_id}")
        print(f"# Plane: {plane_id}")
        print(f"{'#'*70}")
        
        # Run both validation checks
        rail_violations = self.validate_rail_isolation(switch_id, plane_id, actual_neighbors)
        su_violations = self.validate_su_boundary_enforcement(switch_id, actual_neighbors)
        
        total_violations = len(rail_violations) + len(su_violations)
        
        # Determine overall status
        if total_violations == 0:
            status = "PASS"
            cluster_ready = True
            action_required = False
        else:
            status = "CRITICAL"
            cluster_ready = False
            action_required = True
        
        # Extract SU_ID for reporting
        su_id = SUIDExtractor.extract_su_id(switch_id)
        
        # Print final summary
        print(f"\n{'#'*70}")
        print("# VALIDATION SUMMARY")
        print(f"{'#'*70}")
        print(f"Switch: {switch_id}")
        print(f"SU_ID: {su_id}")
        print(f"Plane: {plane_id}")
        print(f"Status: {status}")
        print("")
        print(f"Rail Violations: {len(rail_violations)}")
        print(f"SU Violations: {len(su_violations)}")
        print(f"Total Violations: {total_violations}")
        print("")
        
        if cluster_ready:
            print("✅ CLUSTER READY: All isolation boundaries intact")
        else:
            print(f"🚨 CLUSTER NOT READY: {total_violations} critical violation(s) detected")
            print("⚠️  ACTION REQUIRED: Fix all violations before releasing for compute")
        
        return {
            'switch_id': switch_id,
            'plane_id': plane_id,
            'su_id': su_id,
            'status': status,
            'rail_violations': rail_violations,
            'su_violations': su_violations,
            'total_violations': total_violations,
            'cluster_ready': cluster_ready,
            'action_required': action_required
        }
    
    def _format_gpu_hostname(
        self,
        rack: int,
        server: int,
        gpu: int,
        tail: int
    ) -> str:
        """Format expected GPU hostname in standardized format.
        
        Uses a consistent naming convention that can be parsed back to
        rack/server/GPU components.
        
        Args:
            rack: Rack number (1-indexed)
            server: Server number within rack (1-indexed)
            gpu: GPU number within server (1-indexed)
            tail: NIC tail number (0-indexed)
            
        Returns:
            Formatted hostname string
            
        Example:
            >>> _format_gpu_hostname(rack=1, server=3, gpu=2, tail=0)
            "B200-Rack01-Srv03-GPU2-HCA0"
        """
        return f"B200-Rack{rack:02d}-Srv{server:02d}-GPU{gpu}-HCA{tail}"
    
    def _parse_gpu_hostname(
        self,
        hostname: str
    ) -> Optional[Dict[str, int]]:
        """Parse GPU hostname back to components.
        
        Supports multiple naming conventions:
        - B200-Rack01-Srv03-GPU2-HCA0
        - dgx-r01-s03-gpu2-hca0.cluster.local
        - DGX-R1-S3-G2-H0
        
        Args:
            hostname: GPU hostname string
            
        Returns:
            Dict with {rack, server, gpu, tail} or None if parse fails
            
        Example:
            >>> _parse_gpu_hostname("B200-Rack01-Srv03-GPU2-HCA0")
            {"rack": 1, "server": 3, "gpu": 2, "tail": 0}
        """
        # Try standard format: B200-Rack01-Srv03-GPU2-HCA0
        pattern1 = r'[Bb]200-[Rr]ack(\d+)-[Ss]rv(\d+)-[Gg][Pp][Uu](\d+)-[Hh][Cc][Aa](\d+)'
        match = re.search(pattern1, hostname)
        if match:
            return {
                'rack': int(match.group(1)),
                'server': int(match.group(2)),
                'gpu': int(match.group(3)),
                'tail': int(match.group(4))
            }
        
        # Try compact format: dgx-r01-s03-gpu2-hca0
        pattern2 = r'[Dd][Gg][Xx]-[Rr](\d+)-[Ss](\d+)-[Gg][Pp][Uu](\d+)-[Hh][Cc][Aa](\d+)'
        match = re.search(pattern2, hostname)
        if match:
            return {
                'rack': int(match.group(1)),
                'server': int(match.group(2)),
                'gpu': int(match.group(3)),
                'tail': int(match.group(4))
            }
        
        # Try short format: DGX-R1-S3-G2-H0
        pattern3 = r'[Dd][Gg][Xx]-[Rr](\d+)-[Ss](\d+)-[Gg](\d+)-[Hh](\d+)'
        match = re.search(pattern3, hostname)
        if match:
            return {
                'rack': int(match.group(1)),
                'server': int(match.group(2)),
                'gpu': int(match.group(3)),
                'tail': int(match.group(4))
            }
        
        return None
    
    def _match_neighbor(
        self,
        expected: str,
        actual: str
    ) -> Tuple[bool, Optional[str]]:
        """Fuzzy match expected hostname against actual LLDP hostname.
        
        Handles naming variations and extracts mismatch details.
        
        Args:
            expected: Expected GPU hostname
            actual: Actual hostname from LLDP
            
        Returns:
            Tuple of (is_match, mismatch_details)
            
        Example:
            >>> _match_neighbor(
            ...     "B200-Rack01-Srv03-GPU2-HCA0",
            ...     "dgx-r01-s03-gpu2-hca0.cluster.local"
            ... )
            (True, None)
            
            >>> _match_neighbor(
            ...     "B200-Rack01-Srv01-GPU2-HCA0",
            ...     "B200-Rack01-Srv02-GPU2-HCA0"
            ... )
            (False, "Server mismatch: expected Srv01, got Srv02")
        """
        # Parse both hostnames
        expected_parts = self._parse_gpu_hostname(expected)
        actual_parts = self._parse_gpu_hostname(actual)
        
        if not expected_parts:
            # Can't parse expected - this shouldn't happen
            return False, f"Invalid expected hostname format: {expected}"
        
        if not actual_parts:
            # Can't parse actual - might be different device type
            return False, f"Unrecognized hostname format: {actual} (expected GPU server)"
        
        # Compare components
        mismatches = []
        
        if expected_parts['rack'] != actual_parts['rack']:
            mismatches.append(
                f"Rack mismatch: expected Rack{expected_parts['rack']:02d}, "
                f"got Rack{actual_parts['rack']:02d}"
            )
        
        if expected_parts['server'] != actual_parts['server']:
            mismatches.append(
                f"Server mismatch: expected Srv{expected_parts['server']:02d}, "
                f"got Srv{actual_parts['server']:02d}"
            )
        
        if expected_parts['gpu'] != actual_parts['gpu']:
            mismatches.append(
                f"GPU mismatch: expected GPU{expected_parts['gpu']}, "
                f"got GPU{actual_parts['gpu']}"
            )
        
        if expected_parts['tail'] != actual_parts['tail']:
            mismatches.append(
                f"Tail mismatch: expected HCA{expected_parts['tail']}, "
                f"got HCA{actual_parts['tail']}"
            )
        
        if mismatches:
            return False, "; ".join(mismatches)
        
        return True, None
    
    def _normalize_port_id(self, port_id: str) -> Optional[int]:
        """Normalize vendor-specific port ID to integer.
        
        Handles multiple formats:
        - Arista: "Ethernet1/1" → 1
        - NVIDIA: "p1" → 1
        - Juniper: "et-0/0/1" → 1
        - Cisco: "GigabitEthernet1/0/1" → 1
        
        Args:
            port_id: Vendor-specific port identifier
            
        Returns:
            Port number (1-indexed) or None if parse fails
        """
        # Try simple numeric: "p1", "1"
        match = re.search(r'[pP]?(\d+)$', port_id)
        if match:
            return int(match.group(1))
        
        # Try Arista format: "Ethernet1/1"
        match = re.search(r'Ethernet\d+/(\d+)', port_id)
        if match:
            return int(match.group(1))
        
        # Try Juniper format: "et-0/0/1"
        match = re.search(r'et-\d+/\d+/(\d+)', port_id)
        if match:
            return int(match.group(1))
        
        # Try Cisco format: "GigabitEthernet1/0/1"
        match = re.search(r'GigabitEthernet\d+/\d+/(\d+)', port_id)
        if match:
            return int(match.group(1))
        
        print(f"⚠️  Failed to normalize port ID: {port_id}")
        return None
    
    def _generate_swap_recommendations(
        self,
        results: List[PortValidationResult]
    ) -> List[str]:
        """Generate actionable swap recommendations for symmetric mis-wires.
        
        Detects patterns like:
        - Port 1 has Port 2's cable, Port 2 has Port 1's cable → "Swap cables: Port 1 ↔ Port 2"
        
        Args:
            results: List of validation results
            
        Returns:
            List of swap recommendation strings
        """
        recommendations = []
        
        # Build lookup: expected_neighbor → port_number
        expected_to_port = {}
        for result in results:
            if result.expected_neighbor:
                expected_to_port[result.expected_neighbor] = result.port_number
        
        # Find symmetric swaps
        processed = set()
        
        for result in results:
            if result.status == "FAIL" and result.port_number not in processed:
                # Check if actual neighbor is expected on another port
                if result.actual_neighbor and result.actual_neighbor in expected_to_port:
                    other_port = expected_to_port[result.actual_neighbor]
                    
                    # Find the other port's result
                    other_result = next(
                        (r for r in results if r.port_number == other_port),
                        None
                    )
                    
                    # Check for symmetric swap
                    if (other_result and 
                        other_result.status == "FAIL" and
                        other_result.actual_neighbor == result.expected_neighbor):
                        
                        recommendations.append(
                            f"🔄 Swap cables: Port {result.port_number} ↔ Port {other_port}"
                        )
                        processed.add(result.port_number)
                        processed.add(other_port)
        
        # Add non-symmetric errors
        for result in results:
            if result.status == "FAIL" and result.port_number not in processed:
                recommendations.append(
                    f"❌ Port {result.port_number}: {result.mismatch_details}"
                )
        
        # Add missing cable warnings
        for result in results:
            if result.status == "MISSING":
                recommendations.append(
                    f"⚠️  Port {result.port_number}: No cable detected (expected {result.expected_neighbor})"
                )
        
        return recommendations
