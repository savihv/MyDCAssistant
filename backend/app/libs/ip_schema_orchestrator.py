"""IP Schema Orchestrator for GPU Cluster Deployments.

Implements NVIDIA Mission Control reference architecture for deterministic IP allocation
across 3-tier network fabrics (OOB, Backend InfiniBand, Frontend Ethernet).

Reference Architecture:
- OOB/MGMT: 10.0.0.0/16 (rack-based addressing)
- Backend IB: 100.126.0.0/16 (plane-based addressing with GLOBAL rack IDs)
- Frontend Eth: 100.127.0.0/16 (rack-based addressing)

Key Features:
- Predictable IPs: Installation Lead can guess IP from rack label (10.0.5.42 = Rack-05/U42)
- Multi-Plane Support: InfiniBand switches get 8 IPs (one per rail)
- Multi-SU Support: Global rack IDs prevent IP collisions across Scalable Units
- CSV Override: Manual IPs in CSV take precedence
- Tier-Based Subnets: All Tier-2 spines on same /24 for bulk configuration
"""

import re
from typing import Dict, List, Literal, Optional
from app.libs.cluster_topology import ClusterTopology


NetworkTier = Literal["OOB_MANAGEMENT", "BACKEND_FABRIC", "FRONTEND_FABRIC", "UNKNOWN"]


class IPSchemaOrchestrator:
    """Orchestrates IP allocation following NVIDIA reference architecture.
    
    Supports 3-tier and 4-tier GPU cluster topologies with multi-SU awareness:
    - Tier 1 (Leaf/ToR): Directly connected to B200 nodes
    - Tier 2 (Spine): Aggregates Leafs within a POD (Scalable Unit)
    - Tier 3 (Core/Super-Spine): Interconnects multiple PODs for 4K+ GPUs
    - Tier 4 (Border): External connectivity (optional)
    
    **Multi-SU Global Addressing:**
    Uses ClusterTopology.get_global_rack_id() to ensure IP uniqueness across
    all Scalable Units in a SuperPOD deployment.
    """
    
    # NVIDIA Mission Control Reference Architecture
    SCHEMAS = {
        "OOB_MANAGEMENT": {
            "base": "10.0.0.0/16",
            "strategy": "rack_location",
            "description": "Out-of-band management (BMC, IPMI, switch mgmt)",
            "capacity": 65536,
            "allocation_logic": "10.0.{rack}.{u_pos}"
        },
        "BACKEND_FABRIC": {
            "base": "100.126.0.0/16",
            "strategy": "plane_based",
            "description": "InfiniBand GPU-to-GPU (8 planes for Blackwell)",
            "capacity": 65536,
            "planes": 8,
            "allocation_logic": "100.126.{plane}.{node_id}"
        },
        "FRONTEND_FABRIC": {
            "base": "100.127.0.0/16",
            "strategy": "rack_based",
            "description": "Ethernet storage/data fabric",
            "capacity": 65536,
            "allocation_logic": "100.127.{rack}.{node_id}"
        }
    }
    
    # Switch IP allocation ranges by tier
    SWITCH_IP_RANGES = {
        "leaf": {"start": 1, "end": 200},      # Leaf switches: .1-.200
        "spine": {"start": 250, "end": 254},   # Spine switches: .250-.254
        "core": {"start": 255, "end": 255},    # Core switches: .255
        "super_spine": {"start": 254, "end": 255}  # Super-spine: .254-.255
    }
    
    def __init__(self, topology: Optional[ClusterTopology] = None, cluster_size: str = "4K"):
        """Initialize orchestrator with topology for global IP allocation.
        
        Args:
            topology: ClusterTopology instance for multi-SU global addressing.
                     If None, falls back to local rack-based allocation.
            cluster_size: Cluster size designation (e.g., "4K" for 4096 GPUs)
        """
        self.topology = topology
        self.cluster_size = cluster_size
        self._allocation_tracking: Dict[str, List[str]] = {
            "OOB_MANAGEMENT": [],
            "BACKEND_FABRIC": [],
            "FRONTEND_FABRIC": []
        }
        
        if topology:
            print(f"🌐 IPSchemaOrchestrator initialized for {cluster_size} GPU cluster")
            print(f"   Multi-SU Mode: SU {topology.SU_ID} of {topology.SU_COUNT} (Global Rack Offset: {topology.global_rack_offset})")
        else:
            print(f"🌐 IPSchemaOrchestrator initialized for {cluster_size} GPU cluster (Legacy Mode)")
    
    def generate_ips_for_project(self, devices: List[Dict]) -> List[Dict]:
        """Process device list and assign missing IPs.
        
        This is the main orchestration function. It:
        1. Respects manual IPs from CSV (if provided)
        2. Auto-generates IPs for devices with missing/UNASSIGNED IPs
        3. Handles multi-plane IPs for InfiniBand switches
        4. Tracks allocations for conflict detection
        
        Args:
            devices: List of device dictionaries from CSV or Firestore
            
        Returns:
            Updated device list with IPs assigned
        """
        print(f"\n📡 Orchestrating IP Schema for {len(devices)} devices...")
        
        for idx, device in enumerate(devices):
            device_name = device.get("deviceName", f"device_{idx}")
            
            # Extract network metadata
            network_metadata = device.get("networkMetadata", {})
            tier = network_metadata.get("tier", "UNKNOWN")
            
            # Check if IP is manually provided in CSV
            existing_ip = network_metadata.get("management_ip") or network_metadata.get("managementIp")
            
            if existing_ip and existing_ip not in ["", "UNASSIGNED", None]:
                # CSV override: respect manual IP
                print(f"  ✅ {device_name}: Using CSV-provided IP {existing_ip}")
                network_metadata["management_ip"] = existing_ip
                device["_ip_auto_generated"] = False
                self._allocation_tracking[tier].append(existing_ip)
            else:
                # Auto-generate IP based on tier and role
                print(f"  🎯 {device_name}: Auto-generating IP...")
                
                try:
                    generated_ip = self._calculate_ip(device)
                    network_metadata["management_ip"] = generated_ip
                    device["_ip_auto_generated"] = True
                    self._allocation_tracking[tier].append(generated_ip)
                    print(f"     → {generated_ip} (Tier: {tier})")
                except Exception as e:
                    print(f"     ⚠️ Failed to generate IP: {e}")
                    network_metadata["management_ip"] = "UNASSIGNED"
            
            # For InfiniBand switches, also generate fabric IPs (8 rails)
            if self._is_infiniband_switch(device):
                print(f"  🔢 {device_name}: Generating 8-rail fabric IPs...")
                fabric_ips = self._calculate_fabric_ips(device)
                network_metadata["fabric_ips"] = fabric_ips
                print(f"     → {', '.join(fabric_ips[:3])}... ({len(fabric_ips)} total)")
                
                # Track fabric IPs
                for fabric_ip in fabric_ips:
                    self._allocation_tracking["BACKEND_FABRIC"].append(fabric_ip)
            
            # Update device with modified network metadata
            device["networkMetadata"] = network_metadata
        
        print(f"\n✅ IP orchestration complete: {len(devices)} devices processed")
        return devices
    
    def _calculate_ip(self, device: Dict) -> str:
        """Calculate IP based on device tier, role, and location.
        
        Args:
            device: Device dictionary with location and network metadata
            
        Returns:
            Allocated IP address string
            
        Raises:
            ValueError: If tier is unknown or required fields are missing
        """
        network_metadata = device.get("networkMetadata", {})
        tier = network_metadata.get("tier", "UNKNOWN")
        
        if tier == "UNKNOWN":
            raise ValueError(f"Cannot allocate IP: tier is UNKNOWN for {device.get('deviceName')}")
        
        # Route to tier-specific allocation logic
        if tier == "OOB_MANAGEMENT":
            return self._calculate_oob_ip(device)
        elif tier == "BACKEND_FABRIC":
            return self._calculate_backend_ip(device)
        elif tier == "FRONTEND_FABRIC":
            return self._calculate_frontend_ip(device)
        else:
            raise ValueError(f"Unknown tier: {tier}")
    
    def _calculate_oob_ip(self, device: Dict) -> str:
        """Calculate OOB management IP: 10.0.{rack}.{u_pos}
        
        This makes IPs predictable from physical location:
        - 10.0.5.42 = Rack-05, U42
        - 10.0.12.10 = Rack-12, U10
        
        Installation Lead can guess the IP just by looking at the rack label!
        
        Args:
            device: Device with location info
            
        Returns:
            Management IP in 10.0.0.0/16 range
        """
        location = device.get("location", {})
        rack = location.get("rack", "")
        u_pos = location.get("uPosition", 0)
        
        rack_num = self._extract_rack_number(rack)
        u_pos_num = int(u_pos) if u_pos else 1
        
        # Handle switch role: switches get special IPs
        network_metadata = device.get("networkMetadata", {})
        switch_role = network_metadata.get("switchRole") or network_metadata.get("switch_role")
        
        if switch_role:
            return self._calculate_switch_oob_ip(rack_num, switch_role)
        
        # Standard rack-based allocation
        return f"10.0.{rack_num}.{u_pos_num}"
    
    def _calculate_switch_oob_ip(self, rack_num: int, switch_role: str) -> str:
        """Calculate OOB IP for network switches.
        
        Switch allocation strategy:
        - Leaf/ToR: 10.0.{rack}.250-254 (up to 5 leafs per rack)
        - Spine: 10.0.254.{spine_id} (all spines on same /24 for bulk config)
        - Core: 10.0.255.{core_id} (core switches)
        
        Args:
            rack_num: Rack number
            switch_role: Switch role (leaf, spine, core, super_spine)
            
        Returns:
            Switch management IP
        """
        role = switch_role.lower()
        
        if role in ["leaf", "tor", "leaf_tor"]:
            # Leaf switches in same rack get sequential IPs in .250-.254 range
            # For now, we use first available: .250
            # TODO: Track per-rack leaf count for sequential allocation
            return f"10.0.{rack_num}.250"
        
        elif role in ["spine", "aggregation"]:
            # All spine switches on 10.0.254.0/24 (enables bulk configuration)
            # Use rack number as spine ID for now
            # TODO: Use global spine counter instead of rack
            spine_id = rack_num if rack_num <= 254 else rack_num % 254
            return f"10.0.254.{spine_id}"
        
        elif role in ["core", "super_spine", "superspine"]:
            # Core switches on 10.0.255.0/24
            core_id = rack_num if rack_num <= 254 else rack_num % 254
            return f"10.0.255.{core_id}"
        
        else:
            # Fallback for unknown switch roles
            return f"10.0.{rack_num}.253"
    
    def _calculate_backend_ip(self, device: Dict) -> str:
        """Calculate Backend Fabric IP: 100.126.{plane}.{node_id}
        
        Backend fabric uses plane-based addressing for InfiniBand:
        - 8 planes (rails) for Blackwell architecture
        - Each device gets an IP on its assigned plane
        - Switch management uses plane 0
        
        Args:
            device: Device with network metadata
            
        Returns:
            Backend fabric IP in 100.126.0.0/16 range
        """
        network_metadata = device.get("networkMetadata", {})
        location = device.get("location", {})
        
        # Determine plane assignment (default to 0 for management)
        plane = network_metadata.get("plane_assignment", 0)
        
        # Calculate node ID from rack and U-position
        rack_num = self._extract_rack_number(location.get("rack", ""))
        u_pos = int(location.get("uPosition", 0)) if location.get("uPosition") else 1
        
        # Node ID combines rack and position for uniqueness
        # Example: Rack-05, U10 → node_id = 50 + 10 = 60
        node_id = (rack_num * 50) + u_pos
        
        # Ensure node_id fits in one octet (0-255)
        node_id = node_id % 256
        
        return f"100.126.{plane}.{node_id}"
    
    def generate_gpu_ip(
        self,
        su_rack_id: int,
        server_idx: int,
        gpu_idx: int,
        plane_id: int
    ) -> str:
        """Generate globally unique GPU IP using NVIDIA-compliant addressing.
        
        Implements the formula:
        IP = 100.(126+P).{Global_Rack_ID}.{Server_Index*10 + GPU_Index}
        
        **Why Global Rack ID Matters:**
        In a 4-SU cluster with 8 racks each:
        - SU-1 Rack 1 → Global Rack 1  → 100.126.1.x
        - SU-2 Rack 1 → Global Rack 9  → 100.126.9.x
        - SU-3 Rack 1 → Global Rack 17 → 100.126.17.x
        - SU-4 Rack 1 → Global Rack 25 → 100.126.25.x
        
        This prevents IP collisions and enables Installation Leads to trace
        any IP back to its physical location: 100.126.17.5 → SU-3, Rack 1, Server 0, GPU 5
        
        Args:
            su_rack_id: Rack ID within the SU (1-indexed, local to SU)
            server_idx: Server index within rack (0-indexed)
            gpu_idx: GPU index within server (0-indexed)
            plane_id: Plane ID (0-indexed, typically 0 or 1)
            
        Returns:
            Globally unique GPU IP address
            
        Example:
            >>> # SU-4, Rack 1, Server 1, GPU 4, Plane 0
            >>> orchestrator.generate_gpu_ip(su_rack_id=1, server_idx=1, gpu_idx=4, plane_id=0)
            '100.126.25.14'  # Global Rack 25 (SU-4 offset 24 + local 1)
        """
        if not self.topology:
            raise ValueError(
                "GPU IP generation requires ClusterTopology. "
                "Initialize IPSchemaOrchestrator with topology parameter."
            )
        
        # Convert local SU rack to global cluster rack
        global_rack = self.topology.get_global_rack_id(su_rack_id)
        
        # Calculate plane-specific subnet
        second_octet = 126 + plane_id
        
        # GPU offset within /24 rack subnet
        # Using server_idx * 10 ensures each server gets a block of 10 IPs (for 8 GPUs)
        gpu_offset = (server_idx * 10) + gpu_idx
        
        # Ensure offset fits in one octet
        if gpu_offset > 255:
            raise ValueError(
                f"GPU offset {gpu_offset} exceeds /24 capacity. "
                f"Server {server_idx} GPU {gpu_idx} requires >255 addresses in rack subnet."
            )
        
        ip = f"100.{second_octet}.{global_rack}.{gpu_offset}"
        
        print(f"   🎯 Generated GPU IP: {ip}")
        print(f"      Local Rack: {su_rack_id} → Global Rack: {global_rack}")
        print(f"      Server: {server_idx}, GPU: {gpu_idx}, Plane: {plane_id}")
        
        return ip
    
    def reverse_lookup_gpu_ip(self, ip: str) -> Optional[Dict]:
        """Reverse lookup: IP → (SU, Rack, Server, GPU, Plane)
        
        Enables Installation Leads to troubleshoot errors from IP addresses alone.
        
        Args:
            ip: GPU IP address (e.g., "100.126.25.14")
            
        Returns:
            Dict with location info or None if IP is not a valid GPU IP:
            {
                'su_id': 4,
                'local_rack': 1,
                'global_rack': 25,
                'server_idx': 1,
                'gpu_idx': 4,
                'plane_id': 0,
                'description': 'SU-4, Rack 1, Server 1, GPU 4, Plane 0'
            }
            
        Example:
            >>> orchestrator.reverse_lookup_gpu_ip("100.126.25.14")
            {'su_id': 4, 'local_rack': 1, 'global_rack': 25, 'server_idx': 1, 'gpu_idx': 4, 'plane_id': 0}
        """
        if not self.topology:
            return None
        
        # Parse IP octets
        parts = ip.split(".")
        if len(parts) != 4 or parts[0] != "100":
            return None
        
        try:
            second_octet = int(parts[1])
            global_rack = int(parts[2])
            gpu_offset = int(parts[3])
        except ValueError:
            return None
        
        # Validate plane ID (must be 126 or 127 for GPU traffic)
        if second_octet < 126 or second_octet > 127:
            return None
        
        plane_id = second_octet - 126
        
        # Decode GPU offset
        server_idx = gpu_offset // 10
        gpu_idx = gpu_offset % 10
        
        # Calculate SU and local rack from global rack
        # Global rack formula: global_rack_offset + local_rack
        # Where global_rack_offset = (SU_ID - 1) * racks_per_su
        
        # Find which SU this global rack belongs to
        racks_per_su = self.topology.racks_per_su
        su_id = ((global_rack - 1) // racks_per_su) + 1
        local_rack = ((global_rack - 1) % racks_per_su) + 1
        
        description = f"SU-{su_id}, Rack {local_rack}, Server {server_idx}, GPU {gpu_idx}, Plane {plane_id}"
        
        return {
            'su_id': su_id,
            'local_rack': local_rack,
            'global_rack': global_rack,
            'server_idx': server_idx,
            'gpu_idx': gpu_idx,
            'plane_id': plane_id,
            'description': description
        }
    
    def _calculate_frontend_ip(self, device: Dict) -> str:
        """Calculate Frontend Fabric IP: 100.127.{rack}.{node_id}
        
        Frontend fabric uses rack-based addressing for Ethernet:
        - Each rack gets its own /24 subnet
        - Devices get sequential IPs within rack subnet
        
        Args:
            device: Device with location info
            
        Returns:
            Frontend fabric IP in 100.127.0.0/16 range
        """
        location = device.get("location", {})
        
        rack_num = self._extract_rack_number(location.get("rack", ""))
        u_pos = int(location.get("uPosition", 0)) if location.get("uPosition") else 1
        
        # Use U-position as node ID within rack
        return f"100.127.{rack_num}.{u_pos}"
    
    def _calculate_fabric_ips(self, device: Dict) -> List[str]:
        """Generate 8 fabric IPs for InfiniBand switches (one per rail).
        
        InfiniBand switches in Blackwell architecture have 8 independent
        management planes (rails). Each rail needs its own IP address.
        
        Example for spine switch in Rack-03:
        - Rail 0: 100.126.0.42
        - Rail 1: 100.126.1.42
        - Rail 2: 100.126.2.42
        - ...
        - Rail 7: 100.126.7.42
        
        Args:
            device: InfiniBand switch device
            
        Returns:
            List of 8 IP addresses (one per rail)
        """
        location = device.get("location", {})
        rack_num = self._extract_rack_number(location.get("rack", ""))
        u_pos = int(location.get("uPosition", 0)) if location.get("uPosition") else 1
        
        # Calculate base node ID (same logic as backend IP)
        node_id = (rack_num * 50) + u_pos
        node_id = node_id % 256
        
        # Generate IP for each of 8 planes
        fabric_ips = []
        for plane in range(8):
            fabric_ips.append(f"100.126.{plane}.{node_id}")
        
        return fabric_ips
    
    def _is_infiniband_switch(self, device: Dict) -> bool:
        """Check if device is an InfiniBand switch requiring multi-plane IPs.
        
        Args:
            device: Device to check
            
        Returns:
            True if device is IB switch, False otherwise
        """
        network_metadata = device.get("networkMetadata", {})
        tier = network_metadata.get("tier", "")
        protocol = network_metadata.get("protocol", "").lower()
        device_type = device.get("type", "").lower()
        switch_role = network_metadata.get("switchRole", "").lower()
        
        # Check multiple signals
        is_backend = tier == "BACKEND_FABRIC"
        is_switch = "switch" in device_type or switch_role in ["leaf", "spine", "core"]
        
        # InfiniBand detection from protocol or implicit from backend tier + switch
        has_ib_protocol = "infiniband" in protocol or "ib" in protocol
        
        return is_backend and is_switch and (has_ib_protocol or is_backend)
    
    def _extract_rack_number(self, rack_string: str) -> int:
        """Extract numeric rack number from rack label.
        
        Handles various formats:
        - "Rack-05" → 5
        - "R5" → 5
        - "05" → 5
        - "Rack_12" → 12
        
        Args:
            rack_string: Rack label string
            
        Returns:
            Numeric rack number
        """
        if not rack_string:
            return 0
        
        # Extract first number found in string
        match = re.search(r'(\d+)', str(rack_string))
        if match:
            return int(match.group(1))
        
        # Fallback if no number found
        return 0
    
    def validate_ip_uniqueness(self, devices: List[Dict]) -> Dict:
        """Check for duplicate IP assignments across all devices.
        
        Args:
            devices: List of devices with assigned IPs
            
        Returns:
            Validation report with conflicts list
        """
        print("\n🔍 Validating IP uniqueness...")
        
        ip_map: Dict[str, List[str]] = {}  # ip -> [device_names]
        conflicts = []
        
        for device in devices:
            device_name = device.get("deviceName", "unknown")
            network_metadata = device.get("networkMetadata", {})
            
            # Check management IP
            mgmt_ip = network_metadata.get("management_ip")
            if mgmt_ip and mgmt_ip != "UNASSIGNED":
                if mgmt_ip in ip_map:
                    conflicts.append({
                        "ip": mgmt_ip,
                        "devices": ip_map[mgmt_ip] + [device_name],
                        "type": "management"
                    })
                    ip_map[mgmt_ip].append(device_name)
                else:
                    ip_map[mgmt_ip] = [device_name]
            
            # Check fabric IPs (for InfiniBand switches)
            fabric_ips = network_metadata.get("fabric_ips", [])
            for idx, fabric_ip in enumerate(fabric_ips):
                fabric_label = f"{device_name}-rail{idx}"
                if fabric_ip in ip_map:
                    conflicts.append({
                        "ip": fabric_ip,
                        "devices": ip_map[fabric_ip] + [fabric_label],
                        "type": "fabric"
                    })
                    ip_map[fabric_ip].append(fabric_label)
                else:
                    ip_map[fabric_ip] = [fabric_label]
        
        if conflicts:
            print(f"  ❌ Found {len(conflicts)} IP conflicts")
            for conflict in conflicts[:3]:  # Show first 3
                print(f"     {conflict['ip']}: {', '.join(conflict['devices'])}")
        else:
            print(f"  ✅ No conflicts found ({len(ip_map)} unique IPs)")
        
        return {
            "valid": len(conflicts) == 0,
            "conflicts": conflicts,
            "total_ips": len(ip_map),
            "unique_ips": len([ip for ip, devices in ip_map.items() if len(devices) == 1])
        }
    
    def calculate_subnet_utilization(self, devices: List[Dict]) -> Dict:
        """Track IP usage per tier subnet.
        
        Args:
            devices: List of devices with assigned IPs
            
        Returns:
            Utilization report by tier
        """
        print("\n📊 Calculating subnet utilization...")
        
        # Count IPs by tier
        tier_counts = {
            "OOB_MANAGEMENT": 0,
            "BACKEND_FABRIC": 0,
            "FRONTEND_FABRIC": 0
        }
        
        for device in devices:
            network_metadata = device.get("networkMetadata", {})
            tier = network_metadata.get("tier", "UNKNOWN")
            
            # Count management IP
            if network_metadata.get("management_ip"):
                # For backend fabric, management IP is in OOB tier
                if tier == "BACKEND_FABRIC":
                    tier_counts["OOB_MANAGEMENT"] += 1
                elif tier in tier_counts:
                    tier_counts[tier] += 1
            
            # Count fabric IPs (InfiniBand switches)
            fabric_ips = network_metadata.get("fabric_ips", [])
            if fabric_ips and tier == "BACKEND_FABRIC":
                tier_counts["BACKEND_FABRIC"] += len(fabric_ips)
        
        # Calculate utilization percentages
        utilization = {}
        for tier, schema in self.SCHEMAS.items():
            capacity = schema["capacity"]
            used = tier_counts.get(tier, 0)
            available = capacity - used
            utilization_pct = (used / capacity) * 100 if capacity > 0 else 0
            
            utilization[tier] = {
                "subnet": schema["base"],
                "capacity": capacity,
                "used": used,
                "available": available,
                "utilization_pct": utilization_pct
            }
            
            print(f"  {tier}: {used}/{capacity} ({utilization_pct:.1f}%)")
        
        return utilization
    
    def validate_rack_capacity(self, devices: List[Dict]) -> List[Dict]:
        """Check if any rack exceeds /24 subnet capacity (254 usable IPs).
        
        Args:
            devices: List of devices
            
        Returns:
            List of warnings for over-capacity racks
        """
        print("\n🏗️ Validating rack capacity...")
        
        rack_counts: Dict[str, int] = {}
        
        for device in devices:
            location = device.get("location", {})
            rack = location.get("rack", "UNKNOWN")
            rack_counts[rack] = rack_counts.get(rack, 0) + 1
        
        warnings = []
        for rack, count in rack_counts.items():
            if count > 250:  # 254 usable - 4 buffer for network/broadcast/gateway
                warning = {
                    "rack": rack,
                    "device_count": count,
                    "capacity": 250,
                    "message": f"Rack {rack} has {count} devices, exceeding /24 subnet capacity (250)"
                }
                warnings.append(warning)
                print(f"  ⚠️ {warning['message']}")
        
        if not warnings:
            print(f"  ✅ All racks within capacity ({len(rack_counts)} racks checked)")
        
        return warnings
