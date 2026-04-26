"""Topology Profile - The "DNA" of a GPU Cluster Deployment

This module defines the TopologyProfile class, which encapsulates all the
physical wiring parameters of a GPU cluster. It acts as the "source of truth"
for how many GPUs, servers, racks, and switches exist, and how they connect.

**Purpose:**
- Store cluster topology parameters in Firestore alongside hardware inventory
- Validate topology consistency (e.g., P=N, G divisible by L)
- Calculate port requirements for different switch roles
- Convert to ClusterTopology instances for GPU-to-Leaf mapping

**Usage Pattern:**
1. Installation Lead uploads Asset Inventory CSV with topology parameters
2. TopologyProfile validates parameters and calculates port requirements
3. Each device in Firestore gets tagged with topology DNA
4. During DHCP provisioning, topology is injected into ZTP generation

Example:
    # From API endpoint (CSV upload)
    profile = TopologyProfile(
        gpu_count=8,
        nic_split=2,
        leafs_per_plane=8,
        servers_per_rack=16,
        racks_per_su=8
    )
    profile.validate()  # Raises ValueError if invalid
    
    # Calculate port requirements
    leaf_ports = profile.calculate_required_ports('BACKEND_LEAF')
    # → 128 ports (16 servers × 8 racks)
    
    # Convert to ClusterTopology for IP allocation
    topology = profile.to_cluster_topology()
    mapper = GPUToLeafMapper(topology)
"""

from typing import Dict, Any
from app.libs.cluster_topology import ClusterTopology


class TopologyProfile:
    """GPU cluster topology profile (deployment DNA).
    
    This class stores the fundamental parameters that define a cluster's
    physical wiring topology. It's the bridge between:
    - User-facing configuration (CSV upload)
    - Internal computation (ClusterTopology, GPUToLeafMapper)
    - Storage (Firestore documents)
    
    **Key Invariants:**
    - planes (P) MUST equal nic_split (N)
    - gpu_count (G) MUST be divisible by leafs_per_plane (L)
    - All values must be positive integers
    
    **Attributes:**
        gpu_count (int): GPUs per server (G)
        nic_split (int): NIC tails per GPU (N) - also equals planes (P)
        leafs_per_plane (int): Leaf switches per plane (L)
        servers_per_rack (int): Servers per rack (S)
        racks_per_su (int): Racks per Scalable Unit (R)
    
    **Derived Properties:**
        planes: Number of fabric planes (equals nic_split)
        total_servers: Total servers in cluster (S × R)
        total_gpus: Total GPUs in cluster (G × S × R)
        gpus_per_leaf: GPUs per server connected to each leaf (G ÷ L)
    """
    
    def __init__(
        self,
        gpu_count: int,
        nic_split: int,
        leafs_per_plane: int,
        servers_per_rack: int,
        racks_per_su: int,
        cable_split: int = 1
    ):
        """Initialize topology profile.
        
        Args:
            gpu_count: Number of GPUs per server (e.g., 8 for DGX B200)
            nic_split: NIC tail count per GPU (e.g., 2 for 800G→2×400G)
            leafs_per_plane: Number of leaf switches per plane
            servers_per_rack: Number of servers per rack
            racks_per_su: Number of racks per Scalable Unit
            cable_split: Cable breakout factor (1, 2, or 4)
            
        Raises:
            ValueError: If any parameter is invalid
        """
        self.gpu_count = gpu_count
        self.nic_split = nic_split
        self.leafs_per_plane = leafs_per_plane
        self.servers_per_rack = servers_per_rack
        self.racks_per_su = racks_per_su
        self.cable_split = cable_split
        
        # Derived properties
        self.planes = nic_split  # P = N (critical invariant)
        
        print("📋 Topology Profile Created:")
        print(f"   GPUs/server (G): {gpu_count}")
        print(f"   NIC split (N): {nic_split} (= {self.planes} planes)")
        print(f"   Leafs/plane (L): {leafs_per_plane}")
        print(f"   Servers/rack (S): {servers_per_rack}")
        print(f"   Racks/SU (R): {racks_per_su}")
        print(f"   Cable split: {cable_split}:1")
    
    def validate(self) -> None:
        """Validate topology profile for consistency.
        
        Checks:
        1. All values are positive integers
        2. Planes (P) equals NIC split (N)
        3. GPUs per server (G) is divisible by Leafs per plane (L)
        4. Realistic constraints (e.g., G ≤ 16, N ≤ 8)
        
        Raises:
            ValueError: If validation fails with detailed reason
        """
        # Check positive integers
        if self.gpu_count <= 0:
            raise ValueError(f"gpu_count must be positive, got {self.gpu_count}")
        if self.nic_split <= 0:
            raise ValueError(f"nic_split must be positive, got {self.nic_split}")
        if self.leafs_per_plane <= 0:
            raise ValueError(f"leafs_per_plane must be positive, got {self.leafs_per_plane}")
        if self.servers_per_rack <= 0:
            raise ValueError(f"servers_per_rack must be positive, got {self.servers_per_rack}")
        if self.racks_per_su <= 0:
            raise ValueError(f"racks_per_su must be positive, got {self.racks_per_su}")
        
        # Check critical invariant: P = N
        if self.planes != self.nic_split:
            raise ValueError(
                f"Internal error: planes ({self.planes}) != nic_split ({self.nic_split})"
            )
        
        # Check GPU-to-Leaf divisibility
        if self.gpu_count % self.leafs_per_plane != 0:
            raise ValueError(
                f"gpu_count ({self.gpu_count}) must be divisible by "
                f"leafs_per_plane ({self.leafs_per_plane}). "
                f"Each leaf must connect to an equal number of GPUs per server."
            )
        
        # Realistic constraints
        if self.gpu_count > 16:
            raise ValueError(
                f"gpu_count ({self.gpu_count}) exceeds realistic limit (16). "
                f"Most GPU servers have ≤16 GPUs."
            )
        
        if self.nic_split > 8:
            raise ValueError(
                f"nic_split ({self.nic_split}) exceeds maximum (8). "
                f"InfiniBand supports up to 8 rails."
            )
        
        if self.leafs_per_plane > 16:
            raise ValueError(
                f"leafs_per_plane ({self.leafs_per_plane}) exceeds practical limit (16). "
                f"Consider using spine layer for larger topologies."
            )
        
        gpus_per_leaf = self.gpu_count // self.leafs_per_plane
        print("✅ Topology validation passed")
        print(f"   GPUs per leaf: {gpus_per_leaf}")
        print(f"   Total servers: {self.total_servers}")
        print(f"   Total GPUs: {self.total_gpus}")
    
    @property
    def total_servers(self) -> int:
        """Calculate total servers in cluster."""
        return self.servers_per_rack * self.racks_per_su
    
    @property
    def total_gpus(self) -> int:
        """Calculate total GPUs in cluster."""
        return self.gpu_count * self.total_servers
    
    @property
    def gpus_per_leaf(self) -> int:
        """Calculate GPUs per server that connect to each leaf."""
        return self.gpu_count // self.leafs_per_plane
    
    def calculate_required_ports(self, role: str) -> int:
        """Calculate port count required for a given switch role.
        
        Args:
            role: Switch role (e.g., "BACKEND_LEAF", "BACKEND_SPINE")
            
        Returns:
            Number of data ports required for this role
            
        Example:
            >>> profile = TopologyProfile(G=8, N=2, L=8, S=16, R=8)
            >>> profile.calculate_required_ports('BACKEND_LEAF')
            128  # 16 servers × 8 racks = 128 connections
        """
        if role == "BACKEND_LEAF":
            # Each leaf connects to:
            # - All servers in all racks (each server has gpus_per_leaf GPUs for this leaf)
            # - Total connections = S × R
            return self.servers_per_rack * self.racks_per_su
        
        elif role == "BACKEND_SPINE":
            # Each spine connects to:
            # - All leafs in all planes
            # - Total connections = L × P
            return self.leafs_per_plane * self.planes
        
        elif role == "FRONTEND_LEAF":
            # Frontend (Ethernet) typically has same server connectivity
            return self.servers_per_rack * self.racks_per_su
        
        elif role == "FRONTEND_SPINE":
            # Frontend spine connects to all frontend leafs
            return self.leafs_per_plane
        
        else:
            # Unknown role - return 0 to trigger compatibility check
            print(f"⚠️ Unknown role '{role}', returning 0 required ports")
            return 0
    
    def to_cluster_topology(self) -> ClusterTopology:
        """Convert to ClusterTopology instance for GPU-to-Leaf mapping.
        
        Returns:
            ClusterTopology instance with same parameters
            
        Example:
            >>> profile = TopologyProfile(G=8, N=2, L=8, S=16, R=8)
            >>> topology = profile.to_cluster_topology()
            >>> mapper = GPUToLeafMapper(topology)
        """
        return ClusterTopology(
            G=self.gpu_count,
            N=self.nic_split,
            S=self.servers_per_rack,
            R=self.racks_per_su,
            P=self.planes,
            L=self.leafs_per_plane,
            cable_split=self.cable_split,
            # Multi-SU defaults (single SU deployment)
            SU_ID=1,
            SU_COUNT=1,
            Spines_per_plane=self.leafs_per_plane,  # Non-blocking default
            oversubscription_ratio=1.0
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for Firestore storage.
        
        Returns:
            Dictionary representation of topology profile
            
        Example:
            >>> profile.to_dict()
            {
                'gpu_count': 8,
                'nic_split': 2,
                'leafs_per_plane': 8,
                'servers_per_rack': 16,
                'racks_per_su': 8,
                'cable_split': 1,
                'planes': 2,
                'total_servers': 128,
                'total_gpus': 1024
            }
        """
        return {
            "gpu_count": self.gpu_count,
            "nic_split": self.nic_split,
            "leafs_per_plane": self.leafs_per_plane,
            "servers_per_rack": self.servers_per_rack,
            "racks_per_su": self.racks_per_su,
            "cable_split": self.cable_split,
            "planes": self.planes,
            "total_servers": self.total_servers,
            "total_gpus": self.total_gpus,
            "gpus_per_leaf": self.gpus_per_leaf
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TopologyProfile':
        """Deserialize from Firestore dictionary.
        
        Args:
            data: Dictionary from Firestore document
            
        Returns:
            TopologyProfile instance
            
        Example:
            >>> data = firestore.get_device('SW-RACK01-LEAF1')['topologyProfile']
            >>> profile = TopologyProfile.from_dict(data)
        """
        return cls(
            gpu_count=data['gpu_count'],
            nic_split=data['nic_split'],
            leafs_per_plane=data['leafs_per_plane'],
            servers_per_rack=data['servers_per_rack'],
            racks_per_su=data['racks_per_su'],
            cable_split=data.get('cable_split', 1)  # Default to 1 for backward compatibility
        )
    
    @classmethod
    def create_preset(cls, preset_name: str) -> 'TopologyProfile':
        """Create topology profile from preset name.
        
        Available presets:
        - 'dgx_b200_standard': DGX B200 with 2-plane InfiniBand
        - 'dgx_b200_4plane': DGX B200 with 4-plane InfiniBand
        - 'dgx_h100_standard': DGX H100 with 2-plane InfiniBand
        
        Args:
            preset_name: Name of preset configuration
            
        Returns:
            TopologyProfile instance with preset parameters
            
        Raises:
            ValueError: If preset name is unknown
        """
        presets = {
            'dgx_b200_standard': {
                'gpu_count': 8,
                'nic_split': 2,
                'leafs_per_plane': 8,
                'servers_per_rack': 16,
                'racks_per_su': 8
            },
            'dgx_b200_4plane': {
                'gpu_count': 8,
                'nic_split': 4,
                'leafs_per_plane': 8,
                'servers_per_rack': 16,
                'racks_per_su': 8
            },
            'dgx_h100_standard': {
                'gpu_count': 8,
                'nic_split': 2,
                'leafs_per_plane': 8,
                'servers_per_rack': 16,
                'racks_per_su': 4
            }
        }
        
        if preset_name not in presets:
            raise ValueError(
                f"Unknown preset '{preset_name}'. "
                f"Available: {', '.join(presets.keys())}"
            )
        
        params = presets[preset_name]
        print(f"🎯 Loading preset: {preset_name}")
        return cls(**params)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"TopologyProfile("
            f"G={self.gpu_count}, "
            f"N={self.nic_split}, "
            f"L={self.leafs_per_plane}, "
            f"S={self.servers_per_rack}, "
            f"R={self.racks_per_su}, "
            f"total_gpus={self.total_gpus})"
        )
