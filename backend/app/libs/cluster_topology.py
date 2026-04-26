"""Cluster Topology Model - Defines GPU cluster physical architecture

This module defines the fundamental geometry of a GPU cluster's network fabric.
All IP allocation, port mapping, and provisioning logic derives from these variables.

Key Insight:
    The IP doesn't belong to a switch port - it belongs to a GPU's NIC tail.
    The switch port is configured to EXPECT a specific GPU's IP based on topology.

Example Topologies:
    
    # NVIDIA DGX B200 - 8 GPUs, 1:1 mapping, 2-plane
    ClusterTopology(
        G=8,  # 8 GPUs per server
        N=2,  # 800G NIC split → 2x400G tails
        S=16, # 16 servers per rack
        R=8,  # 8 racks per Scalable Unit
        P=2,  # 2 planes (Tail A, Tail B)
        L=8   # 8 leaf switches per plane (1:1 GPU-to-Leaf)
    )
    
    # Smaller deployment - 4 GPUs, oversubscribed
    ClusterTopology(
        G=8,  # 8 GPUs per server
        N=2,  # 2 tails
        S=16, # 16 servers per rack
        R=4,  # 4 racks
        P=2,  # 2 planes
        L=4   # 4 leaf switches per plane (2:1 oversubscription)
    )
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ClusterTopology:
    """Physical architecture parameters for GPU cluster.
    
    These variables define the entire fabric structure and determine
    how IPs are allocated across the network.
    
    The topology creates a deterministic mapping where:
    - Every GPU knows which leaf switch it connects to
    - Every leaf switch knows which GPUs should be on which ports
    - Every IP encodes {Plane, Leaf, Server, GPU} identity
    
    Attributes:
        SU_ID: Scalable Unit ID (1, 2, 3, ...) - identifies this SU in multi-SU cluster
        SU_COUNT: Total number of SUs in the cluster (e.g., 4 for 16K GPU cluster)
        G: GPUs per server (typically 4 or 8 for B200/H200/H100)
        N: NIC tails per GPU
           - 1 = No split (single 800G link)
           - 2 = Split 800G → 2x400G tails (most common)
           - 4 = Split 1.6T → 4x400G tails (future)
        S: Servers per rack (typically 8-16)
        R: Racks per Scalable Unit (SU)
           - SU is the deployment unit with dedicated spine switches
        P: Planes (always equals N - one plane per NIC tail)
        L: Leaf switches per plane
           - L=G: 1:1 mapping (GPU 1→Leaf 1, GPU 2→Leaf 2, ...)
           - L=G/2: 2:1 oversubscription (GPU 1,2→Leaf 1, GPU 3,4→Leaf 2, ...)
        Spines_per_plane: Spine switches per plane per SU (default: equal to L for non-blocking)
        cable_split: Cable breakout configuration
           - 1 = No split (native port speed, e.g., 64×400G)
           - 2 = 1:2 breakout (e.g., 64 OSFP → 128×200G)
           - 4 = 1:4 breakout (e.g., 64 OSFP → 256×100G)
        oversubscription_ratio: Tier 2→Tier 3 oversubscription (e.g., 2.0 = 2:1)
        name: Human-readable topology name (optional)
        description: Deployment description (optional)
    
    Computed Properties:
        gpus_per_leaf: Number of GPUs from each server connecting to one leaf
        total_servers: S * R (servers in the SU)
        total_gpus: S * R * G (GPUs in the SU)
        total_leaf_switches: L * P (leaf switches in the SU)
        total_spine_switches: Spines_per_plane * P (spine switches in the SU)
        global_rack_offset: Starting rack number for this SU in global cluster
    
    Validation Rules:
        - SU_ID must be >= 1 and <= SU_COUNT
        - P must equal N (planes = NIC tails)
        - G must be divisible by L (even GPU distribution)
        - cable_split must be 1, 2, or 4
        - Spines_per_plane should equal L for non-blocking fabric
        - oversubscription_ratio must be >= 1.0
        - All values must be positive integers
    """
    
    # Server Architecture
    G: int  # GPUs per server
    N: int  # NIC tails per GPU
    S: int  # Servers per rack
    R: int  # Racks per SU
    
    # Fabric Architecture
    P: int  # Planes
    L: int  # Leaf switches per plane
    Spines_per_plane: int = None  # Auto-set to L if None (non-blocking)
    
    # Cable & Oversubscription
    cable_split: int = 1  # Cable breakout factor (1, 2, or 4)
    oversubscription_ratio: float = 1.0  # Tier 2→Tier 3 (1.0 = non-blocking)
    
    name: Optional[str] = None
    description: Optional[str] = None
    
    # Multi-SU Hierarchy
    SU_ID: int = 1  # Scalable Unit ID (default: single SU deployment)
    SU_COUNT: int = 1  # Total SUs in cluster (default: single SU)
    
    def __post_init__(self):
        """Validate topology consistency.
        
        Raises:
            ValueError: If topology parameters are inconsistent
        """
        # Auto-set Spines_per_plane if not specified (non-blocking default)
        if self.Spines_per_plane is None:
            self.Spines_per_plane = self.L
        
        # Validate all core values are positive
        for field_name in ['G', 'N', 'S', 'R', 'P', 'L', 'SU_ID', 'SU_COUNT', 'Spines_per_plane']:
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"{field_name} must be a positive integer, got {value}")
        
        # Validate SU hierarchy
        if self.SU_ID > self.SU_COUNT:
            raise ValueError(
                f"SU_ID ({self.SU_ID}) cannot exceed SU_COUNT ({self.SU_COUNT}). "
                f"This SU is out of bounds for the cluster."
            )
        
        # Validate cable_split parameter
        if self.cable_split not in [1, 2, 4]:
            raise ValueError(
                f"cable_split must be 1 (no split), 2 (1:2 breakout), or 4 (1:4 breakout). "
                f"Got {self.cable_split}"
            )
        
        # Validate oversubscription ratio
        if self.oversubscription_ratio < 1.0:
            raise ValueError(
                f"oversubscription_ratio must be >= 1.0 (1.0 = non-blocking). "
                f"Got {self.oversubscription_ratio}"
            )
        
        # Planes must equal NIC tails (one plane per tail)
        if self.P != self.N:
            raise ValueError(
                f"Planes (P={self.P}) must equal NIC tails (N={self.N}). "
                f"Each NIC tail creates a separate plane."
            )
        
        # GPUs must distribute evenly across leafs
        if self.G % self.L != 0:
            raise ValueError(
                f"GPUs per server (G={self.G}) must be divisible by leafs per plane (L={self.L}). "
                f"Current configuration would leave {self.G % self.L} GPUs without a leaf assignment."
            )
        
        # Sanity check: Spines should equal Leafs for non-blocking fabric
        if self.Spines_per_plane != self.L:
            print(
                f"⚠️ Warning: Spines_per_plane ({self.Spines_per_plane}) != Leafs_per_plane ({self.L}). "
                f"This creates potential blocking and is not recommended for GPU fabrics."
            )
        
        # Calculate derived properties
        self.gpus_per_leaf = self.G // self.L
        
        # Sanity check: oversubscription ratio should be reasonable (1:1 or 2:1)
        if self.gpus_per_leaf > 2:
            print(
                f"⚠️ Warning: High oversubscription ratio detected ({self.gpus_per_leaf}:1). "
                f"Each leaf will handle {self.gpus_per_leaf} GPUs per server. "
                f"This may cause bandwidth contention."
            )
    
    @property
    def total_servers(self) -> int:
        """Total servers in the Scalable Unit.
        
        Returns:
            S * R (servers per rack × racks per SU)
        """
        return self.S * self.R
    
    @property
    def total_gpus(self) -> int:
        """Total GPUs in the Scalable Unit.
        
        Returns:
            S * R * G (total servers × GPUs per server)
        """
        return self.total_servers * self.G
    
    @property
    def total_leaf_switches(self) -> int:
        """Total leaf switches across all planes.
        
        Returns:
            L * P (leafs per plane × planes)
        """
        return self.L * self.P
    
    @property
    def total_spine_switches(self) -> int:
        """Total spine switches across all planes in this SU.
        
        Returns:
            Spines_per_plane * P (spines per plane × planes)
        """
        return self.Spines_per_plane * self.P
    
    @property
    def global_rack_offset(self) -> int:
        """Starting rack number for this SU in the global cluster.
        
        Enables deterministic global addressing across multiple SUs.
        
        Returns:
            (SU_ID - 1) * R
            
        Example:
            - SU-1 (SU_ID=1, R=8): global_rack_offset = 0 (racks 1-8)
            - SU-2 (SU_ID=2, R=8): global_rack_offset = 8 (racks 9-16)
            - SU-3 (SU_ID=3, R=8): global_rack_offset = 16 (racks 17-24)
        """
        return (self.SU_ID - 1) * self.R
    
    @property
    def total_gpus_in_cluster(self) -> int:
        """Total GPUs across all SUs in the cluster.
        
        Returns:
            SU_COUNT * total_gpus
            
        Example:
            - 4 SUs × 1024 GPUs/SU = 4096 GPUs total
        """
        return self.SU_COUNT * self.total_gpus
    
    @property
    def total_nic_interfaces(self) -> int:
        """Total NIC interfaces across all servers.
        
        Returns:
            S * R * G * N (servers × GPUs × NIC tails)
        """
        return self.total_gpus * self.N
    
    def calculate_effective_ports(self, physical_ports: int) -> int:
        """Calculate effective ports after cable breakout.
        
        Args:
            physical_ports: Number of physical OSFP/QSFP connectors on the switch
            
        Returns:
            Effective port count after applying cable_split factor
            
        Example:
            >>> topology = ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8, cable_split=2)
            >>> topology.calculate_effective_ports(64)
            128  # 64 OSFP connectors × 2 (1:2 split) = 128 effective ports
        """
        return physical_ports * self.cable_split
    
    def get_link_speed(self, native_speed_gbps: int) -> int:
        """Calculate link speed after cable split.
        
        Args:
            native_speed_gbps: Native port speed in Gbps (e.g., 400 for 400G)
            
        Returns:
            Effective link speed in Gbps after splitting
            
        Example:
            >>> topology = ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8, cable_split=2)
            >>> topology.get_link_speed(400)
            200  # 400G ÷ 2 = 200G per split port
        """
        return native_speed_gbps // self.cable_split
    
    def get_global_rack_id(self, rack_within_su: int) -> int:
        """Convert local rack ID to global cluster rack ID.
        
        Enables consistent addressing across multiple SUs.
        
        Args:
            rack_within_su: Local rack number within this SU (1 to R)
            
        Returns:
            Global rack ID across the entire cluster
            
        Raises:
            ValueError: If rack_within_su is out of bounds
            
        Example:
            SU-1 (R=8): Rack 1 → Global Rack 1
            SU-2 (R=8): Rack 1 → Global Rack 9
            SU-3 (R=8): Rack 5 → Global Rack 21
        """
        if not (1 <= rack_within_su <= self.R):
            raise ValueError(
                f"Rack {rack_within_su} is out of bounds for SU with {self.R} racks. "
                f"Must be between 1 and {self.R}."
            )
        return self.global_rack_offset + rack_within_su
    
    def get_plane_subnet_prefix(self, plane_id: int) -> str:
        """Get NVIDIA-compliant subnet prefix for a plane.
        
        Implements NVIDIA DGX SuperPOD IP addressing standard:
        - Plane 0: 100.126.x.x
        - Plane 1: 100.127.x.x
        - Plane 2: 100.128.x.x
        - etc.
        
        Args:
            plane_id: Plane number (0 to P-1)
            
        Returns:
            Subnet prefix in format "100.{126+plane_id}"
            
        Raises:
            ValueError: If plane_id is out of bounds
            
        Example:
            >>> topology.get_plane_subnet_prefix(0)
            "100.126"
            >>> topology.get_plane_subnet_prefix(1)
            "100.127"
        """
        if not (0 <= plane_id < self.P):
            raise ValueError(
                f"Plane {plane_id} is out of bounds. Must be between 0 and {self.P-1}."
            )
        base_octet = 126
        return f"100.{base_octet + plane_id}"
    
    def get_summary(self) -> str:
        """Generate human-readable topology summary.
        
        Returns:
            Multi-line string describing the topology
        """
        oversubscription = f"{self.gpus_per_leaf}:1" if self.gpus_per_leaf > 1 else "None (1:1)"
        
        # Cable split description
        if self.cable_split == 1:
            cable_config = "No split (native speed)"
        elif self.cable_split == 2:
            cable_config = "1:2 breakout (half speed)"
        else:  # cable_split == 4
            cable_config = "1:4 breakout (quarter speed)"
        
        # Multi-SU cluster scope
        if self.SU_COUNT > 1:
            cluster_scope = f"Multi-SU Cluster ({self.SU_COUNT} SUs, {self.total_gpus_in_cluster:,} total GPUs)"
            su_info = f"This is SU #{self.SU_ID} (Racks {self.global_rack_offset + 1}-{self.global_rack_offset + self.R})"
        else:
            cluster_scope = "Single SU Deployment"
            su_info = None
        
        summary = """
╭───────────────────────────────────────────────────────────────╮
│ GPU Cluster Topology Summary                                  │
├───────────────────────────────────────────────────────────────┤
"""
        
        if self.name:
            summary += f"│ Name: {self.name:<55} │\n"
        
        summary += f"│ Cluster Scope: {cluster_scope:<48} │\n"
        
        if su_info:
            summary += f"│ SU Position: {su_info:<50} │\n"
        
        summary += f"""│                                                               │
│ Server Architecture:                                          │
│   • GPUs per server (G): {self.G:<39} │
│   • NIC tails per GPU (N): {self.N:<37} │
│   • Servers per rack (S): {self.S:<38} │
│                                                               │
│ Scalable Unit (SU) Layout:                                    │
│   • Racks per SU (R): {self.R:<42} │
│   • Total servers: {self.total_servers:<45} │
│   • Total GPUs: {self.total_gpus:<48} │
│                                                               │
│ Network Fabric (Tier 1 - Leaf):                               │
│   • Planes (P): {self.P:<48} │
│   • Leaf switches per plane (L): {self.L:<31} │
│   • Total leaf switches: {self.total_leaf_switches:<38} │
│   • Oversubscription: {oversubscription:<42} │
│   • GPUs per leaf: {self.gpus_per_leaf:<45} │
│   • Cable configuration: {cable_config:<38} │
│                                                               │
│ Network Fabric (Tier 2 - Spine):                              │
│   • Spines per plane: {self.Spines_per_plane:<42} │
│   • Total spine switches: {self.total_spine_switches:<38} │
│   • Tier 2→Tier 3 oversubscription: {self.oversubscription_ratio:<21} │
│                                                               │
│ Total Network Endpoints:                                      │
│   • GPU NIC interfaces: {self.total_nic_interfaces:<38} │
╰───────────────────────────────────────────────────────────────╯
"""
        return summary


# Common topology presets for quick deployment
COMMON_TOPOLOGIES = {
    "dgx-b200-standard": ClusterTopology(
        G=8, N=2, S=16, R=8, P=2, L=8,
        cable_split=1,  # 400G native (no split)
        name="NVIDIA DGX B200 Standard",
        description="8 GPUs per server, 1:1 GPU-to-Leaf mapping, 2 planes"
    ),
    
    "dgx-h100-standard": ClusterTopology(
        G=8, N=2, S=16, R=8, P=2, L=8,
        cable_split=1,  # 400G native (no split)
        name="NVIDIA DGX H100 Standard",
        description="8 GPUs per server, 1:1 GPU-to-Leaf mapping, 2 planes"
    ),
    
    "dgx-oversubscribed": ClusterTopology(
        G=8, N=2, S=16, R=4, P=2, L=4,
        cable_split=1,  # 400G native (no split)
        name="DGX Oversubscribed",
        description="8 GPUs per server, 2:1 oversubscription, 2 planes"
    ),
    
    "small-4gpu": ClusterTopology(
        G=4, N=2, S=16, R=4, P=2, L=4,
        cable_split=1,  # 400G native (no split)
        name="Small 4-GPU Deployment",
        description="4 GPUs per server, 1:1 GPU-to-Leaf mapping, 2 planes"
    ),
}


def get_topology_preset(preset_name: str) -> ClusterTopology:
    """Get a pre-defined topology configuration.
    
    Args:
        preset_name: Name of the preset (e.g., 'dgx-b200-standard')
        
    Returns:
        ClusterTopology instance
        
    Raises:
        KeyError: If preset_name not found
    """
    if preset_name not in COMMON_TOPOLOGIES:
        available = ', '.join(COMMON_TOPOLOGIES.keys())
        raise KeyError(
            f"Topology preset '{preset_name}' not found. "
            f"Available presets: {available}"
        )
    
    return COMMON_TOPOLOGIES[preset_name]
