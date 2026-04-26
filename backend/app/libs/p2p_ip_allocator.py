"""Point-to-Point IP Allocator - Deterministic /31 Subnet Assignment

Assigns /31 point-to-point subnets to GPU NIC tails following
NVIDIA Mission Control reference architecture for GPU clusters.

**CRITICAL ARCHITECTURE CHANGE:**
IPs are no longer allocated per switch port. They are allocated per GPU NIC tail.
The switch port is configured to EXPECT a specific GPU's IP based on topology.

Key Principles:
- Backend (InfiniBand): 100.126-133.0.0/16 - GPU-to-GPU fabric (8 planes)
- Frontend (Ethernet): 100.140-141.0.0/16 - Storage/data plane
- OOB Management: 10.0.0.0/16 - Out-of-band management
- /31 subnets: Each link gets 2 IPs (no network/broadcast overhead)
- GPU-aware: IP encodes {Plane, Leaf, Rack, Server, GPU}

IP Formula for GPU NIC Tail:
    100.{126+tail}.{(rack-1)*L + leaf_id}.{(server-1)*2}/31

Example:
    allocator = P2PIPAllocator()
    topology = ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8)
    mapper = GPUToLeafMapper(topology)
    
    # Allocate IP for GPU 1, Tail 0 on Server 5 in Rack 2
    ip = allocator.allocate_gpu_ip(
        rack_num=2,
        server_num=5,
        gpu_num=1,
        tail_num=0,
        topology=topology,
        mapper=mapper
    )
    # → Returns "100.126.9.8/31" (Plane 0, Leaf 1, Rack 2, Server 5)
"""

import ipaddress
from typing import Dict, Tuple, List
from app.libs.cluster_topology import ClusterTopology
from app.libs.gpu_to_leaf_mapper import GPUToLeafMapper


class P2PIPAllocator:
    """Allocates /31 point-to-point IPs for GPU NIC tails and switch ports.
    
    **NEW GPU-Aware Architecture:**
    This allocator now supports two modes:
    
    1. GPU-Aware Allocation (PREFERRED):
       - allocate_gpu_ip(): Single GPU interface IP
       - allocate_server_ips(): All GPU interfaces on a server
       - allocate_leaf_port_ips(): All expected connections to a leaf switch
    
    2. Legacy Switch-Port Allocation (DEPRECATED):
       - allocate_port_ip(): Simple port-based allocation
       - allocate_port_range(): Range of ports
    
    Use GPU-aware methods for InfiniBand backend fabric.
    Use legacy methods for management/OOB networks.
    """
    
    # NVIDIA Reference Architecture Subnets (Non-Routable Private IP Ranges)
    SUBNET_RANGES = {
        # Management Plane (OOB)
        "OOB_MGMT": "10.0.0.0/16",
        
        # Backend Fabric (InfiniBand) - Multi-Plane Architecture
        # Each plane gets its own /16 subnet to support 4K+ GPU clusters
        "BACKEND_PLANE0": "100.126.0.0/16",  # Tail 0 (Plane 0)
        "BACKEND_PLANE1": "100.127.0.0/16",  # Tail 1 (Plane 1)
        "BACKEND_PLANE2": "100.128.0.0/16",  # Tail 2 (Plane 2) - future
        "BACKEND_PLANE3": "100.129.0.0/16",  # Tail 3 (Plane 3) - future
        "BACKEND_PLANE4": "100.130.0.0/16",  # Tail 4 (Plane 4) - future
        "BACKEND_PLANE5": "100.131.0.0/16",  # Tail 5 (Plane 5) - future
        "BACKEND_PLANE6": "100.132.0.0/16",  # Tail 6 (Plane 6) - future
        "BACKEND_PLANE7": "100.133.0.0/16",  # Tail 7 (Plane 7) - future
        
        # Frontend Fabric (Ethernet) - Storage/Data Plane
        "FRONTEND_LEAF": "100.140.0.0/16",
        "FRONTEND_SPINE": "100.141.0.0/16",
    }
    
    def __init__(self):
        """Initialize the P2P IP allocator."""
        print("🔢 P2PIPAllocator initialized (GPU-aware mode)")
    
    # ============== NEW: GPU-Aware IP Allocation ==============
    
    def allocate_gpu_ip(
        self,
        rack_num: int,
        server_num: int,
        gpu_num: int,
        tail_num: int,
        topology: ClusterTopology,
        mapper: GPUToLeafMapper
    ) -> str:
        """Allocate IP for a specific GPU's NIC tail.
        
        This is the NEW main entry point for GPU-aware IP allocation.
        The IP encodes the GPU's identity and which leaf it connects to.
        
        Args:
            rack_num: Rack number (1-based)
            server_num: Server number within rack (1-based)
            gpu_num: GPU number within server (1-based: 1..G)
            tail_num: NIC tail (0-based: 0 for Plane 0, 1 for Plane 1, etc.)
            topology: Cluster topology configuration
            mapper: GPU-to-Leaf mapper instance
            
        Returns:
            IP address with /31 prefix (e.g., "100.126.9.8/31")
            
        Raises:
            ValueError: If any parameter is out of range
            
        Example:
            >>> # Topology: G=8, N=2, S=16, R=8, P=2, L=8
            >>> # Rack 2, Server 5, GPU 1, Tail 0
            >>> ip = allocator.allocate_gpu_ip(2, 5, 1, 0, topology, mapper)
            >>> print(ip)
            "100.126.9.8/31"
            
            Explanation:
            - Octet 2 (126): Plane 0 (tail 0)
            - Octet 3 (9): Leaf block = (2-1)*8 + 1 = 9
            - Octet 4 (8): Server offset = (5-1)*2 = 8
        """
        # Validate inputs
        if rack_num < 1 or rack_num > topology.R:
            raise ValueError(f"Rack number {rack_num} out of range [1..{topology.R}]")
        
        if server_num < 1 or server_num > topology.S:
            raise ValueError(f"Server number {server_num} out of range [1..{topology.S}]")
        
        if gpu_num < 1 or gpu_num > topology.G:
            raise ValueError(f"GPU number {gpu_num} out of range [1..{topology.G}]")
        
        if tail_num < 0 or tail_num >= topology.N:
            raise ValueError(f"Tail number {tail_num} out of range [0..{topology.N-1}]")
        
        # Octet 2: Plane (based on tail)
        plane_octet = 126 + tail_num  # 126, 127, 128, ...
        
        # Determine which leaf this GPU connects to
        leaf_id = mapper.get_leaf_id_for_gpu(gpu_num)
        
        # Octet 3: Leaf block = (rack-1)*L + leaf_id
        # This ensures all servers in same rack connecting to same leaf are in same /24
        leaf_block_octet = (rack_num - 1) * topology.L + leaf_id
        
        # Octet 4: Server endpoint = (server-1)*2 (using /31 subnets)
        # Each /31 has 2 IPs: .0 (server side) and .1 (switch side)
        endpoint_octet = (server_num - 1) * 2
        
        # Construct final IP
        ip = f"100.{plane_octet}.{leaf_block_octet}.{endpoint_octet}/31"
        
        return ip
    
    def allocate_server_ips(
        self,
        rack_num: int,
        server_num: int,
        topology: ClusterTopology,
        mapper: GPUToLeafMapper
    ) -> List[Dict]:
        """Allocate IPs for all GPU interfaces on a server.
        
        Returns a complete IP matrix for one server showing:
        - Which GPU each IP belongs to
        - Which NIC tail (plane)
        - Which leaf switch it connects to
        - The allocated IP address
        
        Args:
            rack_num: Rack number
            server_num: Server number within rack
            topology: Cluster topology
            mapper: GPU-to-Leaf mapper
            
        Returns:
            List of dicts with keys:
            - gpu: GPU number (1..G)
            - tail: Tail number (0..N-1)
            - plane: Plane ID (equals tail)
            - leaf: Target leaf ID (1..L)
            - ip: Allocated IP address
            - target_leaf_switch: Human-readable leaf identifier
            
        Example:
            >>> # Server 5 in Rack 2, topology with G=8, N=2, L=8
            >>> ips = allocator.allocate_server_ips(2, 5, topology, mapper)
            >>> ips[0]
            {
                'gpu': 1,
                'tail': 0,
                'plane': 0,
                'leaf': 1,
                'ip': '100.126.9.8/31',
                'target_leaf_switch': 'Leaf-P0-L1'
            }
            >>> ips[1]
            {
                'gpu': 1,
                'tail': 1,
                'plane': 1,
                'leaf': 1,
                'ip': '100.127.9.8/31',
                'target_leaf_switch': 'Leaf-P1-L1'
            }
            >>> len(ips)
            16  # 8 GPUs × 2 tails = 16 interfaces
        """
        allocations = []
        
        for gpu_num in range(1, topology.G + 1):
            for tail_num in range(topology.N):
                ip = self.allocate_gpu_ip(
                    rack_num=rack_num,
                    server_num=server_num,
                    gpu_num=gpu_num,
                    tail_num=tail_num,
                    topology=topology,
                    mapper=mapper
                )
                
                leaf_id = mapper.get_leaf_id_for_gpu(gpu_num)
                
                allocations.append({
                    "gpu": gpu_num,
                    "tail": tail_num,
                    "plane": tail_num,
                    "leaf": leaf_id,
                    "ip": ip,
                    "target_leaf_switch": f"Leaf-P{tail_num}-L{leaf_id}",
                    "description": f"GPU{gpu_num}-Tail{tail_num} → Leaf-P{tail_num}-L{leaf_id}"
                })
        
        return allocations
    
    def allocate_leaf_port_ips(
        self,
        plane_id: int,
        leaf_id: int,
        topology: ClusterTopology,
        mapper: GPUToLeafMapper
    ) -> List[Dict]:
        """Allocate IPs for all expected connections to a leaf switch.
        
        Returns the complete port-to-IP mapping for a leaf switch.
        This is used by JITZTPGenerator to configure switch ports.
        
        Args:
            plane_id: Plane ID (0-based: 0..P-1)
            leaf_id: Leaf ID within plane (1-based: 1..L)
            topology: Cluster topology
            mapper: GPU-to-Leaf mapper
            
        Returns:
            List of dicts with keys:
            - port_number: Physical port on switch
            - rack: Expected rack number
            - server: Expected server number
            - gpu: Expected GPU number
            - server_ip: IP address on server side (/31 .0)
            - switch_ip: IP address on switch side (/31 .1)
            - subnet: Full /31 subnet
            - description: Port description
            
        Example:
            >>> # Leaf 1 in Plane 0
            >>> port_ips = allocator.allocate_leaf_port_ips(0, 1, topology, mapper)
            >>> port_ips[0]
            {
                'port_number': 1,
                'rack': 1,
                'server': 1,
                'gpu': 1,
                'server_ip': '100.126.1.0',
                'switch_ip': '100.126.1.1',
                'subnet': '100.126.1.0/31',
                'description': 'GPU1-Rack1-Srv1-Tail0'
            }
        """
        # Get expected port mappings from mapper
        port_mappings = mapper.get_port_mapping_for_leaf(plane_id, leaf_id)
        
        allocations = []
        
        for mapping in port_mappings:
            # Calculate IP for this connection
            subnet_ip = self.allocate_gpu_ip(
                rack_num=mapping['rack'],
                server_num=mapping['server'],
                gpu_num=mapping['gpu'],
                tail_num=plane_id,
                topology=topology,
                mapper=mapper
            )
            
            # Parse /31 subnet to get server and switch IPs
            network = ipaddress.IPv4Network(subnet_ip, strict=False)
            server_ip = str(network.network_address)  # .0 address
            switch_ip = str(network.network_address + 1)  # .1 address
            
            allocations.append({
                "port_number": mapping['port_number'],
                "rack": mapping['rack'],
                "server": mapping['server'],
                "gpu": mapping['gpu'],
                "server_ip": server_ip,
                "switch_ip": switch_ip,
                "subnet": subnet_ip,
                "description": mapping['description']
            })
        
        return allocations
    
    def get_peer_ip_from_gpu_ip(self, gpu_ip: str) -> str:
        """Get the switch-side IP for a GPU's /31 subnet.
        
        In a /31 subnet:
        - .0 address: Assigned to server/GPU
        - .1 address: Assigned to switch port
        
        Args:
            gpu_ip: GPU's IP address with /31 prefix
            
        Returns:
            Switch-side IP address
            
        Example:
            >>> allocator.get_peer_ip_from_gpu_ip("100.126.9.8/31")
            "100.126.9.9"
        """
        network = ipaddress.IPv4Network(gpu_ip, strict=False)
        
        # In /31, if GPU has .0, switch has .1 (and vice versa)
        gpu_addr = ipaddress.IPv4Address(gpu_ip.split('/')[0])
        
        if gpu_addr == network.network_address:
            return str(network.network_address + 1)
        else:
            return str(network.network_address)
    
    # ============== LEGACY: Switch-Port-Based Allocation (DEPRECATED) ==============
    # These methods are kept for backward compatibility with management networks
    
    def allocate_port_ip(self, switch_id: str, role: str, port_number: int) -> str:
        """Allocate /31 IP address for a specific switch port.
        
        This is the main entry point for IP allocation. Given a switch identity
        and port number, it returns a deterministic /31 subnet.
        
        Args:
            switch_id: Switch identifier (e.g., "SW-RACK04-LEAF1")
            role: Switch role (e.g., "BACKEND_LEAF", "FRONTEND_SPINE")
            port_number: Physical port number (1-based)
            
        Returns:
            IP address with /31 prefix (e.g., "100.126.4.0/31")
            
        Raises:
            ValueError: If role is unknown or switch_id is malformed
            
        Example:
            >>> allocator.allocate_port_ip("SW-RACK04-LEAF1", "BACKEND_LEAF", 1)
            "100.126.4.0/31"
            
            >>> allocator.allocate_port_ip("SW-RACK04-LEAF1", "BACKEND_LEAF", 2)
            "100.126.4.2/31"
        """
        if role not in self.SUBNET_RANGES:
            raise ValueError(f"Unknown switch role: {role}")
        
        # Extract rack number and switch tier from switch_id
        rack_num, tier = self._parse_switch_id(switch_id)
        
        # Calculate base IP for this switch
        base_ip = self._calculate_base_ip(role, rack_num, tier)
        
        # Calculate port-specific offset (/31 uses 2 IPs per port)
        # Port 1 → .0/.1, Port 2 → .2/.3, Port 3 → .4/.5, etc.
        port_offset = (port_number - 1) * 2
        
        # Construct final IP
        final_ip = base_ip + port_offset
        ip_with_prefix = f"{final_ip}/31"
        
        return ip_with_prefix
    
    def allocate_port_range(self, switch_id: str, role: str, port_count: int) -> list[Dict]:
        """Allocate IPs for all ports on a switch.
        
        Convenience method for getting all port IPs at once.
        Used by JITZTPGenerator to build complete config scripts.
        
        Args:
            switch_id: Switch identifier
            role: Switch role
            port_count: Number of data ports on the switch
            
        Returns:
            List of dicts with 'port_number' and 'ip_address' keys
            
        Example:
            >>> allocator.allocate_port_range("SW-RACK04-LEAF1", "BACKEND_LEAF", 64)
            [
                {"port_number": 1, "ip_address": "100.126.4.0/31"},
                {"port_number": 2, "ip_address": "100.126.4.2/31"},
                ...
                {"port_number": 64, "ip_address": "100.126.4.126/31"}
            ]
        """
        allocations = []
        
        for port_num in range(1, port_count + 1):
            ip_addr = self.allocate_port_ip(switch_id, role, port_num)
            allocations.append({
                "port_number": port_num,
                "ip_address": ip_addr
            })
        
        return allocations
    
    def _parse_switch_id(self, switch_id: str) -> Tuple[int, str]:
        """Extract rack number and tier from switch ID.
        
        Parses switch IDs like:
        - "SW-RACK04-LEAF1" → rack=4, tier="LEAF"
        - "SW-R05-SPINE2" → rack=5, tier="SPINE"
        - "IB-RACK03-LEAF4" → rack=3, tier="LEAF"
        
        Args:
            switch_id: Switch identifier string
            
        Returns:
            Tuple of (rack_number, tier)
            
        Raises:
            ValueError: If switch_id format is invalid
        """
        import re
        
        # Match patterns like "RACK04" or "R05"
        rack_match = re.search(r'R(?:ACK)?(\d+)', switch_id, re.IGNORECASE)
        if not rack_match:
            raise ValueError(f"Cannot extract rack number from switch_id: {switch_id}")
        
        rack_num = int(rack_match.group(1))
        
        # Match tier (LEAF, SPINE, CORE)
        tier_match = re.search(r'(LEAF|SPINE|CORE)', switch_id, re.IGNORECASE)
        if tier_match:
            tier = tier_match.group(1).upper()
        else:
            # Default to LEAF if not specified
            tier = "LEAF"
        
        return rack_num, tier
    
    def _calculate_base_ip(self, role: str, rack_num: int, tier: str) -> ipaddress.IPv4Address:
        """Calculate base IP address for a switch.
        
        The base IP is the starting point for port allocations.
        Each port adds an offset to this base.
        
        Strategy:
        - LEAF switches: Use rack number in 3rd octet
        - SPINE switches: Use 128 + spine_id in 3rd octet
        - CORE switches: Use 192 + core_id in 3rd octet
        
        Args:
            role: Switch role (e.g., "BACKEND_LEAF")
            rack_num: Rack number extracted from switch_id
            tier: Switch tier (LEAF, SPINE, CORE)
            
        Returns:
            Base IPv4 address for this switch
            
        Example:
            >>> _calculate_base_ip("BACKEND_LEAF", 4, "LEAF")
            IPv4Address('100.126.4.0')
        """
        base_network = ipaddress.IPv4Network(self.SUBNET_RANGES[role])
        
        if tier == "LEAF":
            # LEAF: 100.126.{rack}.0
            third_octet = rack_num
        elif tier == "SPINE":
            # SPINE: 100.126.{128+rack}.0
            third_octet = 128 + rack_num
        elif tier == "CORE":
            # CORE: 100.126.{192+rack}.0
            third_octet = 192 + rack_num
        else:
            third_octet = rack_num
        
        # Construct IP: base_network.first_octet.base_network.second_octet.third_octet.0
        # For BACKEND_LEAF: 100.126.{rack}.0
        base_octets = str(base_network.network_address).split('.')
        base_ip = f"{base_octets[0]}.{base_octets[1]}.{third_octet}.0"
        
        return ipaddress.IPv4Address(base_ip)
    
    def get_peer_ip(self, switch_ip: str) -> str:
        """Get the peer IP for a /31 point-to-point link.
        
        /31 subnets have exactly 2 usable IPs:
        - .0 → typically the "local" side
        - .1 → typically the "remote" side
        
        Args:
            switch_ip: IP address with /31 prefix (e.g., "100.126.4.0/31")
            
        Returns:
            Peer IP address (e.g., "100.126.4.1/31")
            
        Example:
            >>> allocator.get_peer_ip("100.126.4.0/31")
            "100.126.4.1/31"
            
            >>> allocator.get_peer_ip("100.126.4.1/31")
            "100.126.4.0/31"
        """
        ip = ipaddress.IPv4Interface(switch_ip)
        
        # Get the network address (base of /31 subnet)
        network = ip.network
        
        # /31 has exactly 2 addresses: .0 and .1
        if ip.ip == network.network_address:
            peer = network.network_address + 1
        else:
            peer = network.network_address
        
        return f"{peer}/31"
    
    def validate_allocation(self, switch_id: str, role: str, port_count: int) -> Dict:
        """Validate that IP allocation won't overflow subnet.
        
        Ensures that the switch's port count doesn't exceed the
        available IP space in its assigned subnet.
        
        Args:
            switch_id: Switch identifier
            role: Switch role
            port_count: Number of ports to allocate
            
        Returns:
            Dict with validation results:
            - valid: bool
            - required_ips: int (port_count * 2 for /31)
            - available_ips: int
            - overflow: bool
            
        Example:
            >>> allocator.validate_allocation("SW-RACK04-LEAF1", "BACKEND_LEAF", 64)
            {"valid": True, "required_ips": 128, "available_ips": 254, "overflow": False}
        """
        required_ips = port_count * 2  # /31 uses 2 IPs per port
        
        # Each switch gets a /24 subnet (254 usable IPs)
        available_ips = 254
        
        overflow = required_ips > available_ips
        valid = not overflow
        
        return {
            "valid": valid,
            "required_ips": required_ips,
            "available_ips": available_ips,
            "overflow": overflow,
            "max_ports": available_ips // 2
        }
