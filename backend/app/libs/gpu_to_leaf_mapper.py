"""GPU-to-Leaf Mapper - Determines which GPU connects to which leaf switch

This module implements the critical mapping logic that ensures every GPU
knows which leaf switch it should connect to based on cluster topology.

Key Insight:
    In a GPU cluster, connections are NOT arbitrary. GPU 1 from EVERY server
    connects to Leaf 1 in each plane. This creates a deterministic fabric
    where mis-wiring can be detected automatically.

Mapping Examples:
    
    # 8 GPUs, 8 Leafs per plane (1:1 mapping)
    GPU 1 → Leaf 1
    GPU 2 → Leaf 2
    ...
    GPU 8 → Leaf 8
    
    # 8 GPUs, 4 Leafs per plane (2:1 oversubscription)
    GPU 1, 2 → Leaf 1
    GPU 3, 4 → Leaf 2
    GPU 5, 6 → Leaf 3
    GPU 7, 8 → Leaf 4

Use Cases:
    - IP Allocation: Calculate which subnet block a GPU's IP belongs to
    - ZTP Generation: Configure switch ports with expected GPU connections
    - Mis-Wiring Detection: Validate physical cabling against topology
    - Troubleshooting: "Why is GPU 5 not training?" → Check Leaf 5 status
"""

from app.libs.cluster_topology import ClusterTopology
from typing import List, Dict


class GPUToLeafMapper:
    """Maps GPU identities to target leaf switches based on cluster topology.
    
    This class implements the core routing logic for GPU fabric connections.
    Every GPU knows which leaf it connects to, and every leaf knows which
    GPUs should be on which ports.
    
    The mapper is topology-aware and handles different oversubscription ratios:
    - 1:1 (G=L): Each GPU gets its own leaf
    - 2:1 (G=2*L): Two GPUs share each leaf
    - Higher ratios supported but not recommended
    
    Example:
        >>> topology = ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8)
        >>> mapper = GPUToLeafMapper(topology)
        >>> mapper.get_leaf_id_for_gpu(5)
        5  # GPU 5 connects to Leaf 5
        
        >>> mapper.get_gpus_for_leaf(3)
        [3]  # Leaf 3 expects GPU 3 from all servers
    """
    
    def __init__(self, topology: ClusterTopology):
        """Initialize mapper with cluster topology.
        
        Args:
            topology: ClusterTopology instance defining network geometry
        """
        self.topology = topology
        self.gpus_per_leaf = topology.gpus_per_leaf
        
        print("🗺️ GPUToLeafMapper initialized")
        print(f"   Topology: {topology.G} GPUs → {topology.L} Leafs per plane")
        print(f"   Oversubscription: {self.gpus_per_leaf}:1")
    
    def get_leaf_id_for_gpu(self, gpu_index: int) -> int:
        """Determine which leaf switch a GPU connects to within a plane.
        
        This is the core mapping function. Given a GPU number within a server,
        it returns which leaf switch that GPU connects to.
        
        Args:
            gpu_index: GPU number within server (1-based: 1, 2, ..., G)
            
        Returns:
            Leaf switch ID within plane (1-based: 1, 2, ..., L)
            
        Raises:
            ValueError: If gpu_index is out of range
            
        Examples:
            >>> # 8 GPUs, 8 Leafs (1:1)
            >>> mapper.get_leaf_id_for_gpu(1)  # GPU 1 → Leaf 1
            1
            >>> mapper.get_leaf_id_for_gpu(8)  # GPU 8 → Leaf 8
            8
            
            >>> # 8 GPUs, 4 Leafs (2:1)
            >>> mapper.get_leaf_id_for_gpu(1)  # GPU 1 → Leaf 1
            1
            >>> mapper.get_leaf_id_for_gpu(2)  # GPU 2 → Leaf 1 (shared)
            1
            >>> mapper.get_leaf_id_for_gpu(3)  # GPU 3 → Leaf 2
            2
        """
        if gpu_index < 1 or gpu_index > self.topology.G:
            raise ValueError(
                f"GPU index {gpu_index} out of range [1..{self.topology.G}]. "
                f"This topology supports {self.topology.G} GPUs per server."
            )
        
        # Calculate which leaf this GPU maps to
        # Formula: leaf_id = ceil(gpu_index / gpus_per_leaf)
        # Equivalent: ((gpu_index - 1) // gpus_per_leaf) + 1
        leaf_id = ((gpu_index - 1) // self.gpus_per_leaf) + 1
        
        return leaf_id
    
    def get_gpus_for_leaf(self, leaf_id: int) -> List[int]:
        """Get all GPU indices that connect to a specific leaf.
        
        This is the inverse of get_leaf_id_for_gpu. Given a leaf switch,
        it returns which GPU slots from each server should connect to it.
        
        Args:
            leaf_id: Leaf switch ID within plane (1-based: 1..L)
            
        Returns:
            List of GPU indices (e.g., [1, 2] for 2:1 oversubscription)
            
        Raises:
            ValueError: If leaf_id is out of range
            
        Examples:
            >>> # 8 GPUs, 8 Leafs (1:1)
            >>> mapper.get_gpus_for_leaf(5)
            [5]  # Only GPU 5 connects to Leaf 5
            
            >>> # 8 GPUs, 4 Leafs (2:1)
            >>> mapper.get_gpus_for_leaf(1)
            [1, 2]  # GPU 1 and 2 both connect to Leaf 1
            >>> mapper.get_gpus_for_leaf(4)
            [7, 8]  # GPU 7 and 8 both connect to Leaf 4
        """
        if leaf_id < 1 or leaf_id > self.topology.L:
            raise ValueError(
                f"Leaf ID {leaf_id} out of range [1..{self.topology.L}]. "
                f"This topology has {self.topology.L} leaf switches per plane."
            )
        
        # Calculate the range of GPUs for this leaf
        start_gpu = (leaf_id - 1) * self.gpus_per_leaf + 1
        end_gpu = start_gpu + self.gpus_per_leaf
        
        return list(range(start_gpu, end_gpu))
    
    def get_port_mapping_for_leaf(
        self, 
        plane_id: int, 
        leaf_id: int
    ) -> List[Dict]:
        """Generate expected port mappings for a leaf switch.
        
        Returns the complete port-to-server mapping for a leaf switch.
        This tells the switch which server's GPU should be on each port.
        
        Used by JITZTPGenerator to configure switch ports with:
        - Expected IP address
        - Port description (for troubleshooting)
        - LLDP validation rules
        
        Args:
            plane_id: Plane ID (0-based: 0..P-1)
            leaf_id: Leaf ID within plane (1-based: 1..L)
            
        Returns:
            List of dicts with keys:
            - port_number: Physical port on switch (1-based)
            - rack: Expected rack number
            - server: Expected server number within rack
            - gpu: Expected GPU number within server
            - tail: Expected NIC tail (0 or 1)
            - description: Human-readable port description
            
        Example:
            >>> # Leaf 1 in Plane 0, topology with 2 racks, 2 servers per rack
            >>> mappings = mapper.get_port_mapping_for_leaf(0, 1)
            >>> mappings[0]
            {
                'port_number': 1,
                'rack': 1,
                'server': 1,
                'gpu': 1,  # GPU 1 from Rack 1, Server 1
                'tail': 0,
                'description': 'GPU1-Rack1-Srv1-Tail0'
            }
            >>> mappings[1]
            {
                'port_number': 2,
                'rack': 1,
                'server': 2,
                'gpu': 1,  # GPU 1 from Rack 1, Server 2
                'tail': 0,
                'description': 'GPU1-Rack1-Srv2-Tail0'
            }
        """
        if plane_id < 0 or plane_id >= self.topology.P:
            raise ValueError(
                f"Plane ID {plane_id} out of range [0..{self.topology.P-1}]. "
                f"This topology has {self.topology.P} planes."
            )
        
        # Get which GPU slot(s) connect to this leaf
        gpus_for_this_leaf = self.get_gpus_for_leaf(leaf_id)
        
        mappings = []
        port_num = 1
        
        # Iterate through all racks and servers in the SU
        for rack in range(1, self.topology.R + 1):
            for server in range(1, self.topology.S + 1):
                # Each server connects multiple GPUs to this leaf (based on oversubscription)
                for gpu in gpus_for_this_leaf:
                    mappings.append({
                        "port_number": port_num,
                        "rack": rack,
                        "server": server,
                        "gpu": gpu,
                        "tail": plane_id,
                        "description": f"GPU{gpu}-Rack{rack}-Srv{server}-Tail{plane_id}"
                    })
                    port_num += 1
        
        return mappings
    
    def get_leaf_port_for_server(
        self, 
        leaf_id: int,
        rack_num: int, 
        server_num: int,
        gpu_num: int
    ) -> int:
        """Calculate which port on a leaf a specific server's GPU connects to.
        
        This is the inverse of get_port_mapping_for_leaf. Given a server's
        identity, it returns which physical port on the leaf it should be
        connected to.
        
        Args:
            leaf_id: Leaf switch ID (1-based)
            rack_num: Rack number (1-based)
            server_num: Server number within rack (1-based)
            gpu_num: GPU number within server (1-based)
            
        Returns:
            Port number on the leaf switch (1-based)
            
        Raises:
            ValueError: If GPU doesn't connect to this leaf
            
        Example:
            >>> # Server 5 in Rack 2, GPU 1 connecting to Leaf 1
            >>> # Topology: R=8 racks, S=16 servers/rack, L=8 leafs, 1:1 mapping
            >>> mapper.get_leaf_port_for_server(1, 2, 5, 1)
            21  # Port 21 = (Rack 2, Server 5, GPU 1)
            
        Calculation:
            Port = ((rack - 1) * servers_per_rack + (server - 1)) * gpus_per_leaf + gpu_offset + 1
            Where gpu_offset is the position of this GPU within the leaf's GPU group
        """
        # Verify this GPU connects to this leaf
        expected_leaf = self.get_leaf_id_for_gpu(gpu_num)
        if expected_leaf != leaf_id:
            raise ValueError(
                f"GPU {gpu_num} does not connect to Leaf {leaf_id}. "
                f"It connects to Leaf {expected_leaf}."
            )
        
        # Calculate server index within SU (0-based)
        server_index_in_su = (rack_num - 1) * self.topology.S + (server_num - 1)
        
        # Calculate GPU offset within the leaf's GPU group
        gpus_for_leaf = self.get_gpus_for_leaf(leaf_id)
        gpu_offset = gpus_for_leaf.index(gpu_num)
        
        # Calculate port number (1-based)
        port_num = server_index_in_su * self.gpus_per_leaf + gpu_offset + 1
        
        return port_num
    
    def validate_connection(
        self,
        leaf_id: int,
        port_num: int,
        detected_gpu: int,
        rack_num: int,
        server_num: int
    ) -> Dict:
        """Validate if a detected GPU connection matches the expected topology.
        
        Used for mis-wiring detection. When LLDP/CDP discovers a GPU on a
        switch port, this validates if it's the CORRECT GPU for that port.
        
        Args:
            leaf_id: Leaf switch ID where connection was detected
            port_num: Port number where GPU was detected
            detected_gpu: GPU number detected via LLDP/CDP
            rack_num: Rack number of the server
            server_num: Server number within rack
            
        Returns:
            Dict with keys:
            - valid: bool (True if connection is correct)
            - expected_gpu: int (GPU that should be on this port)
            - detected_gpu: int (GPU that was actually detected)
            - error_type: str or None ("wrong_gpu", "wrong_port", etc.)
            - message: str (human-readable explanation)
            
        Example:
            >>> # Port 21 on Leaf 1 detected GPU 5 (should be GPU 1)
            >>> result = mapper.validate_connection(1, 21, 5, 2, 5)
            >>> result
            {
                'valid': False,
                'expected_gpu': 1,
                'detected_gpu': 5,
                'error_type': 'wrong_gpu',
                'message': 'Expected GPU 1, detected GPU 5. Cable likely plugged into wrong leaf.'
            }
        """
        # Get expected port mapping for this leaf
        mappings = self.get_port_mapping_for_leaf(0, leaf_id)  # Plane doesn't matter for validation
        
        # Find the mapping for this port
        port_mapping = next((m for m in mappings if m['port_number'] == port_num), None)
        
        if not port_mapping:
            return {
                "valid": False,
                "expected_gpu": None,
                "detected_gpu": detected_gpu,
                "error_type": "invalid_port",
                "message": f"Port {port_num} exceeds leaf capacity. This leaf has {len(mappings)} ports."
            }
        
        expected_gpu = port_mapping['gpu']
        expected_rack = port_mapping['rack']
        expected_server = port_mapping['server']
        
        # Check if everything matches
        if (expected_gpu == detected_gpu and 
            expected_rack == rack_num and 
            expected_server == server_num):
            return {
                "valid": True,
                "expected_gpu": expected_gpu,
                "detected_gpu": detected_gpu,
                "error_type": None,
                "message": f"Connection valid: GPU {detected_gpu} from Rack {rack_num}, Server {server_num}"
            }
        
        # Detect specific error types
        if expected_gpu != detected_gpu:
            return {
                "valid": False,
                "expected_gpu": expected_gpu,
                "detected_gpu": detected_gpu,
                "error_type": "wrong_gpu",
                "message": (
                    f"Expected GPU {expected_gpu}, detected GPU {detected_gpu}. "
                    f"Cable from Rack {rack_num}, Server {server_num} likely plugged into wrong leaf. "
                    f"GPU {detected_gpu} should connect to Leaf {self.get_leaf_id_for_gpu(detected_gpu)}."
                )
            }
        
        if expected_rack != rack_num or expected_server != server_num:
            return {
                "valid": False,
                "expected_gpu": expected_gpu,
                "detected_gpu": detected_gpu,
                "error_type": "wrong_server",
                "message": (
                    f"Port {port_num} expects Rack {expected_rack}, Server {expected_server} "
                    f"but detected Rack {rack_num}, Server {server_num}."
                )
            }
        
        return {
            "valid": False,
            "expected_gpu": expected_gpu,
            "detected_gpu": detected_gpu,
            "error_type": "unknown",
            "message": "Connection validation failed for unknown reason."
        }
