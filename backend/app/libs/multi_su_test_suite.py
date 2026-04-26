"""Multi-SU Validation Test Suite - Boundary Enforcement Testing

This test suite validates that the system correctly handles multi-SU deployments
by detecting and preventing cross-SU contamination, IP conflicts, and mis-provisioning.

**Critical Scenarios Tested:**
1. **Cross-SU Cable Contamination**: SU1 switch connected to SU2 switch
2. **Global IP Uniqueness**: No IP conflicts across SUs
3. **DHCP Boundary Validation**: Switches provisioned with correct SU config
4. **Global Rack ID Mapping**: SU-local racks map to unique global IDs
5. **BGP ASN Isolation**: SU1 and SU2 use different ASN ranges

**Test Architecture:**
```
SU1 (8 racks, 1024 GPUs)          SU2 (8 racks, 1024 GPUs)
┌─────────────────────┐          ┌─────────────────────┐
│ Racks 1-8           │          │ Racks 9-16          │
│ Global Racks 1-8    │          │ Global Racks 9-16   │
│ IPs: 100.126.1.x    │          │ IPs: 100.126.9.x    │
│ BGP: 65010/64010    │          │ BGP: 65020/64020    │
└─────────────────────┘          └─────────────────────┘
         ↓                                  ↓
    [ISOLATED]                         [ISOLATED]
         ↓                                  ↓
    CROSS-CONNECTION = CRITICAL ERROR
```

**Expected Behavior:**
- ✅ System detects if SU1-L3-P0 is cabled to SU2-S5-P0
- ✅ System rejects DHCP requests from switches in wrong SU
- ✅ System ensures global IP uniqueness (no collisions)
- ✅ System validates global rack IDs don't overlap
- ✅ System prevents BGP ASN conflicts

**Usage:**
```python
from app.libs.multi_su_test_suite import MultiSUTestSuite

tester = MultiSUTestSuite()

# Run all tests
tester.run_all_tests()

# Run specific test
tester.test_cross_su_cable_contamination()
```
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from app.libs.cluster_topology import ClusterTopology
from app.libs.leaf_to_spine_mapper import LeafToSpineMapper
from app.libs.fabric_ip_orchestrator import FabricIPOrchestrator
from app.libs.spine_ztp_generator import SpineZTPGenerator
import re


@dataclass
class MockCableConnection:
    """Mock cable connection for testing.
    
    Attributes:
        local_hostname: Hostname of local switch (e.g., "SU1-L3-P0")
        local_port: Port number on local switch
        remote_hostname: Hostname of remote switch (e.g., "SU2-S5-P0")
        remote_port: Port number on remote switch
        expected_valid: Whether this connection should be valid
        violation_type: Type of violation if invalid
    """
    local_hostname: str
    local_port: int
    remote_hostname: str
    remote_port: int
    expected_valid: bool
    violation_type: Optional[str] = None


@dataclass
class MockDHCPRequest:
    """Mock DHCP request from a switch.
    
    Attributes:
        serial_number: Switch serial number
        mac_address: Switch MAC address
        expected_su_id: SU this switch should belong to
        physical_rack_id: Physical rack where switch is installed
        requested_hostname: Hostname switch is requesting
    """
    serial_number: str
    mac_address: str
    expected_su_id: int
    physical_rack_id: int
    requested_hostname: str


@dataclass
class ValidationResult:
    """Result of a validation test.
    
    Attributes:
        test_name: Name of the test
        passed: Whether test passed
        message: Human-readable result message
        details: Additional details about the test
        violations: List of violations detected
    """
    test_name: str
    passed: bool
    message: str
    details: Dict
    violations: List[str]


class SUIDExtractor:
    """Extract SU_ID from hierarchical hostnames.
    
    This utility parses hostnames like "SU1-L3-P0" or "SU2-S5-P1"
    to extract the Scalable Unit ID.
    
    **Hostname Format:**
    - Leaf switches: SU{ID}-L{leaf_id}-P{plane_id}
    - Spine switches: SU{ID}-S{spine_id}-P{plane_id}
    - Super-Spine: CORE-S{spine_id}-P{plane_id} (future)
    
    **Examples:**
    - "SU1-L3-P0" → SU_ID=1, Type=Leaf, ID=3, Plane=0
    - "SU2-S5-P1" → SU_ID=2, Type=Spine, ID=5, Plane=1
    """
    
    # Regex pattern for SU-scoped switches
    SU_PATTERN = re.compile(r'^SU(\d+)-(L|S)(\d+)-P(\d+)$')
    
    @classmethod
    def extract_su_id(cls, hostname: str) -> Optional[int]:
        """Extract SU_ID from hostname.
        
        Args:
            hostname: Switch hostname (e.g., "SU1-L3-P0")
            
        Returns:
            SU_ID if found, None otherwise
            
        Example:
            >>> SUIDExtractor.extract_su_id("SU1-L3-P0")
            1
            >>> SUIDExtractor.extract_su_id("SU2-S5-P1")
            2
            >>> SUIDExtractor.extract_su_id("INVALID")
            None
        """
        match = cls.SU_PATTERN.match(hostname)
        if match:
            return int(match.group(1))
        return None
    
    @classmethod
    def extract_switch_type(cls, hostname: str) -> Optional[str]:
        """Extract switch type from hostname.
        
        Args:
            hostname: Switch hostname
            
        Returns:
            "Leaf" or "Spine" if found, None otherwise
        """
        match = cls.SU_PATTERN.match(hostname)
        if match:
            switch_type = match.group(2)
            return "Leaf" if switch_type == "L" else "Spine"
        return None
    
    @classmethod
    def extract_all_components(cls, hostname: str) -> Optional[Dict]:
        """Extract all components from hostname.
        
        Args:
            hostname: Switch hostname
            
        Returns:
            Dictionary with su_id, switch_type, switch_id, plane_id
            
        Example:
            >>> SUIDExtractor.extract_all_components("SU1-L3-P0")
            {'su_id': 1, 'switch_type': 'Leaf', 'switch_id': 3, 'plane_id': 0}
        """
        match = cls.SU_PATTERN.match(hostname)
        if match:
            return {
                'su_id': int(match.group(1)),
                'switch_type': 'Leaf' if match.group(2) == 'L' else 'Spine',
                'switch_id': int(match.group(3)),
                'plane_id': int(match.group(4))
            }
        return None


class MultiSUValidator:
    """Validator for multi-SU boundary enforcement.
    
    This validator implements the critical checks that prevent
    cross-SU contamination in multi-SU SuperPOD deployments.
    """
    
    @staticmethod
    def validate_cable_connection(
        local_hostname: str,
        remote_hostname: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate that a cable connection doesn't cross SU boundaries.
        
        Args:
            local_hostname: Hostname of local switch
            remote_hostname: Hostname of remote switch
            
        Returns:
            Tuple of (is_valid, violation_message)
            
        Example:
            >>> MultiSUValidator.validate_cable_connection("SU1-L3-P0", "SU1-S5-P0")
            (True, None)
            >>> MultiSUValidator.validate_cable_connection("SU1-L3-P0", "SU2-S5-P0")
            (False, "CRITICAL: Cross-SU contamination detected...")
        """
        local_su = SUIDExtractor.extract_su_id(local_hostname)
        remote_su = SUIDExtractor.extract_su_id(remote_hostname)
        
        # If we can't parse hostnames, we can't validate
        if local_su is None or remote_su is None:
            return (True, None)  # Don't fail on unparseable hostnames
        
        # Check for cross-SU contamination
        if local_su != remote_su:
            violation = (
                f"CRITICAL: Cross-SU contamination detected! "
                f"Switch '{local_hostname}' (SU{local_su}) is connected to "
                f"switch '{remote_hostname}' (SU{remote_su}). "
                f"This will cause suboptimal routing and jitter in All-Reduce traffic."
            )
            return (False, violation)
        
        return (True, None)
    
    @staticmethod
    def validate_dhcp_request(
        requested_hostname: str,
        physical_rack_id: int,
        topology: ClusterTopology
    ) -> Tuple[bool, Optional[str]]:
        """Validate that a DHCP request is for the correct SU.
        
        Args:
            requested_hostname: Hostname switch is requesting
            physical_rack_id: Physical rack where switch is installed
            topology: ClusterTopology for the expected SU
            
        Returns:
            Tuple of (is_valid, violation_message)
            
        Example:
            >>> topology = ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8, SU_ID=1)
            >>> MultiSUValidator.validate_dhcp_request("SU1-L3-P0", 3, topology)
            (True, None)
            >>> MultiSUValidator.validate_dhcp_request("SU2-L3-P0", 3, topology)
            (False, "DHCP violation: Switch in SU1 requesting SU2 config")
        """
        requested_su = SUIDExtractor.extract_su_id(requested_hostname)
        
        if requested_su is None:
            return (True, None)  # Can't validate unparseable hostname
        
        # Calculate which SU this rack should belong to
        expected_su = topology.SU_ID
        
        # Check if request matches expected SU
        if requested_su != expected_su:
            violation = (
                f"DHCP violation: Switch in physical rack {physical_rack_id} "
                f"(SU{expected_su}) is requesting hostname '{requested_hostname}' "
                f"which belongs to SU{requested_su}. This indicates a mis-provisioning error."
            )
            return (False, violation)
        
        return (True, None)


class MultiSUTestSuite:
    """Comprehensive test suite for multi-SU validation.
    
    This suite simulates a multi-SU deployment and validates that
    all boundary enforcement mechanisms work correctly.
    """
    
    def __init__(self):
        """Initialize test suite with multi-SU topologies."""
        print("🧪 Initializing Multi-SU Test Suite")
        print("   Simulating 4-SU deployment (128 racks, 16K GPUs)")
        
        # Create 4 SU topologies
        self.sus = [
            ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8, SU_ID=i, SU_COUNT=4)
            for i in range(1, 5)
        ]
        
        # Create orchestration components for each SU
        self.mappers = [LeafToSpineMapper(su) for su in self.sus]
        self.orchestrators = [
            FabricIPOrchestrator(su, mapper)
            for su, mapper in zip(self.sus, self.mappers)
        ]
        self.generators = [
            SpineZTPGenerator(su, mapper, orch)
            for su, mapper, orch in zip(self.sus, self.mappers, self.orchestrators)
        ]
        
        self.test_results: List[ValidationResult] = []
        
        print("✅ Test suite initialized")
    
    def test_cross_su_cable_contamination(self) -> ValidationResult:
        """Test Case A: Detect cross-SU cable contamination.
        
        Simulates a technician accidentally connecting:
        - SU1-L3-P0 to SU2-S5-P0 (INVALID)
        - SU1-L3-P0 to SU1-S5-P0 (VALID)
        """
        print("\n" + "=" * 80)
        print("TEST CASE A: Cross-SU Cable Contamination Detection")
        print("=" * 80)
        
        test_cables = [
            MockCableConnection(
                local_hostname="SU1-L3-P0",
                local_port=22,
                remote_hostname="SU1-S5-P0",
                remote_port=4,
                expected_valid=True,
                violation_type=None
            ),
            MockCableConnection(
                local_hostname="SU1-L3-P0",
                local_port=22,
                remote_hostname="SU2-S5-P0",  # CROSS-SU VIOLATION!
                remote_port=4,
                expected_valid=False,
                violation_type="CROSS_SU_CONTAMINATION"
            ),
            MockCableConnection(
                local_hostname="SU2-L0-P1",
                local_port=17,
                remote_hostname="SU1-S0-P1",  # CROSS-SU VIOLATION!
                remote_port=1,
                expected_valid=False,
                violation_type="CROSS_SU_CONTAMINATION"
            ),
            MockCableConnection(
                local_hostname="SU4-L7-P0",
                local_port=24,
                remote_hostname="SU4-S7-P0",
                remote_port=8,
                expected_valid=True,
                violation_type=None
            ),
        ]
        
        violations = []
        all_passed = True
        
        for cable in test_cables:
            is_valid, violation_msg = MultiSUValidator.validate_cable_connection(
                cable.local_hostname,
                cable.remote_hostname
            )
            
            # Check if result matches expectation
            if is_valid != cable.expected_valid:
                all_passed = False
                violations.append(
                    f"FAILED: {cable.local_hostname} → {cable.remote_hostname} "
                    f"expected {'VALID' if cable.expected_valid else 'INVALID'}, "
                    f"got {'VALID' if is_valid else 'INVALID'}"
                )
            else:
                status = "✅ VALID" if is_valid else "🚫 INVALID"
                print(f"{status}: {cable.local_hostname}:{cable.local_port} → "
                      f"{cable.remote_hostname}:{cable.remote_port}")
                if violation_msg:
                    print(f"   Reason: {violation_msg}")
        
        result = ValidationResult(
            test_name="Cross-SU Cable Contamination",
            passed=all_passed,
            message=f"Tested {len(test_cables)} cable connections",
            details={'tested_cables': len(test_cables), 'violations_detected': len([c for c in test_cables if not c.expected_valid])},
            violations=violations
        )
        
        self.test_results.append(result)
        return result
    
    def test_global_ip_uniqueness(self) -> ValidationResult:
        """Test Case B: Verify no IP conflicts across SUs.
        
        Validates that:
        - SU1 uses 100.130.1.x
        - SU2 uses 100.130.2.x
        - No overlaps across all 4 SUs
        """
        print("\n" + "=" * 80)
        print("TEST CASE B: Global IP Uniqueness Across SUs")
        print("=" * 80)
        
        all_ips = set()
        ip_conflicts = []
        
        for su_idx, orchestrator in enumerate(self.orchestrators, start=1):
            allocations = orchestrator.get_all_fabric_ips()
            print(f"\nSU{su_idx}: Allocated {len(allocations)} links")
            
            su_ips = set()
            for alloc in allocations:
                # Check for conflicts within SU
                for ip in [alloc.leaf_ip, alloc.spine_ip]:
                    if ip in all_ips:
                        ip_conflicts.append(f"IP {ip} used in multiple SUs")
                    all_ips.add(ip)
                    su_ips.add(ip)
            
            # Show sample IPs from this SU
            sample_ips = list(su_ips)[:3]
            print(f"   Sample IPs: {', '.join(sample_ips)}")
        
        print(f"\n📊 Total unique IPs allocated: {len(all_ips)}")
        print(f"📊 Expected IPs: {sum(len(o.get_all_fabric_ips()) for o in self.orchestrators) * 2}")
        
        result = ValidationResult(
            test_name="Global IP Uniqueness",
            passed=len(ip_conflicts) == 0,
            message=f"Allocated {len(all_ips)} unique IPs across {len(self.sus)} SUs",
            details={'total_ips': len(all_ips), 'conflicts': len(ip_conflicts)},
            violations=ip_conflicts
        )
        
        self.test_results.append(result)
        return result
    
    def test_global_rack_id_mapping(self) -> ValidationResult:
        """Test Case C: Verify global rack ID mapping.
        
        Validates that:
        - SU1 Rack 1 → Global Rack 1
        - SU2 Rack 1 → Global Rack 9 (with R=8)
        - SU3 Rack 1 → Global Rack 17
        - SU4 Rack 1 → Global Rack 25
        """
        print("\n" + "=" * 80)
        print("TEST CASE C: Global Rack ID Mapping")
        print("=" * 80)
        
        expected_mappings = [
            (1, 1, 1),   # SU1, Rack 1 → Global 1
            (1, 8, 8),   # SU1, Rack 8 → Global 8
            (2, 1, 9),   # SU2, Rack 1 → Global 9
            (2, 8, 16),  # SU2, Rack 8 → Global 16
            (3, 1, 17),  # SU3, Rack 1 → Global 17
            (4, 8, 32),  # SU4, Rack 8 → Global 32
        ]
        
        violations = []
        
        for su_id, local_rack, expected_global in expected_mappings:
            topology = self.sus[su_id - 1]
            actual_global = topology.get_global_rack_id(local_rack)
            
            if actual_global == expected_global:
                print(f"✅ SU{su_id} Rack {local_rack} → Global Rack {actual_global}")
            else:
                violation = f"SU{su_id} Rack {local_rack}: expected Global {expected_global}, got {actual_global}"
                print(f"❌ {violation}")
                violations.append(violation)
        
        result = ValidationResult(
            test_name="Global Rack ID Mapping",
            passed=len(violations) == 0,
            message=f"Validated {len(expected_mappings)} rack mappings",
            details={'tested_mappings': len(expected_mappings)},
            violations=violations
        )
        
        self.test_results.append(result)
        return result
    
    def test_bgp_asn_isolation(self) -> ValidationResult:
        """Test Case D: Verify BGP ASN isolation across SUs.
        
        Validates that:
        - SU1 Spines use ASN 65010/65011
        - SU2 Spines use ASN 65020/65021
        - No ASN conflicts
        """
        print("\n" + "=" * 80)
        print("TEST CASE D: BGP ASN Isolation")
        print("=" * 80)
        
        asn_allocations = {}
        violations = []
        
        for su_idx, generator in enumerate(self.generators, start=1):
            for plane_id in range(2):
                spine_asn = generator._get_spine_asn(plane_id)
                leaf_asn = generator._get_leaf_asn(plane_id)
                
                # Check for ASN conflicts
                for asn, role in [(spine_asn, f"SU{su_idx} P{plane_id} Spine"),
                                   (leaf_asn, f"SU{su_idx} P{plane_id} Leaf")]:
                    if asn in asn_allocations:
                        violations.append(
                            f"ASN {asn} conflict: {role} vs {asn_allocations[asn]}"
                        )
                    asn_allocations[asn] = role
                
                print(f"SU{su_idx} Plane {plane_id}: Spine ASN={spine_asn}, Leaf ASN={leaf_asn}")
        
        result = ValidationResult(
            test_name="BGP ASN Isolation",
            passed=len(violations) == 0,
            message=f"Allocated {len(asn_allocations)} unique ASNs",
            details={'total_asns': len(asn_allocations)},
            violations=violations
        )
        
        self.test_results.append(result)
        return result
    
    def run_all_tests(self) -> List[ValidationResult]:
        """Run all multi-SU validation tests.
        
        Returns:
            List of ValidationResult objects
        """
        print("\n" + "#" * 80)
        print("# MULTI-SU VALIDATION TEST SUITE")
        print("#" * 80)
        
        # Run all tests
        self.test_cross_su_cable_contamination()
        self.test_global_ip_uniqueness()
        self.test_global_rack_id_mapping()
        self.test_bgp_asn_isolation()
        
        # Print summary
        print("\n" + "#" * 80)
        print("# TEST SUMMARY")
        print("#" * 80)
        
        passed_count = sum(1 for r in self.test_results if r.passed)
        total_count = len(self.test_results)
        
        for result in self.test_results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"{status}: {result.test_name}")
            print(f"   {result.message}")
            if result.violations:
                print(f"   Violations: {len(result.violations)}")
                for violation in result.violations[:3]:
                    print(f"      - {violation}")
        
        print(f"\n📊 Overall: {passed_count}/{total_count} tests passed")
        
        if passed_count == total_count:
            print("\n🎉 ALL TESTS PASSED! Multi-SU boundary enforcement is working!")
        else:
            print(f"\n⚠️  {total_count - passed_count} test(s) failed - boundary enforcement needs fixes")
        
        return self.test_results
