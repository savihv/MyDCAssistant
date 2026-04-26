"""Leaf-to-Spine Mapper - Deterministic Tier 1 to Tier 2 Uplink Mapping

This module implements the uplink mapping logic for NVIDIA DGX SuperPOD reference
architecture, enabling deterministic connections between Leaf (Tier 1) and Spine
(Tier 2) switches within a Scalable Unit.

**Architecture:**
- Tier 1 (Leaf): Top-of-Rack switches connecting to GPU servers
- Tier 2 (Spine): SU-scoped aggregation layer
- Tier 3 (Super-Spine/Core): Cross-SU interconnect (future phase)

**Key Principle - Full Mesh Within Plane:**
Each Leaf switch in a plane connects to ALL Spine switches in the SAME plane.
This creates a non-blocking fabric where any GPU can reach any other GPU with
equal bandwidth.

Example (L=8 leafs, S=8 spines per plane):
  Plane 0, Leaf 3 has 8 uplinks:
    - Uplink 0 → Spine 0, Port 3
    - Uplink 1 → Spine 1, Port 3
    - Uplink 2 → Spine 2, Port 3
    - ... (symmetric for all 8 spines)

**Hierarchical Naming Convention:**
- Leaf:  SU{SU_ID}-L{leaf_id}-P{plane_id}  (e.g., "SU1-L3-P0")
- Spine: SU{SU_ID}-S{spine_id}-P{plane_id} (e.g., "SU2-S5-P1")
- Super-Spine: CORE-S{spine_id}-P{plane_id} (cross-SU, future)

**Usage:**
    from app.libs.cluster_topology import ClusterTopology
    from app.libs.leaf_to_spine_mapper import LeafToSpineMapper
    
    topology = ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8)
    mapper = LeafToSpineMapper(topology)
    
    # Get uplink mapping for a specific leaf
    uplinks = mapper.get_uplink_mapping(leaf_id=3, plane_id=0)
    for conn in uplinks:
        print(f"Uplink {conn.uplink_port} → {conn.spine_name} Port {conn.spine_port}")
    
    # Get downlink mapping for a specific spine
    downlinks = mapper.get_spine_downlinks(spine_id=5, plane_id=0)
    for conn in downlinks:
        print(f"Downlink {conn.downlink_port} → {conn.leaf_name} Port {conn.leaf_port}")
"""

from dataclasses import dataclass
from typing import List
from app.libs.cluster_topology import ClusterTopology


@dataclass
class UplinkConnection:
    """Represents a leaf switch uplink connection to a spine switch.
    
    Attributes:
        uplink_port: Physical uplink port number on the leaf switch (0-indexed)
        spine_id: Target spine switch ID (0 to Spines_per_plane-1)
        spine_port: Downlink port number on the spine switch (0-indexed)
        plane_id: Plane/rail this connection belongs to (0 to P-1)
        leaf_name: Hierarchical leaf switch name (e.g., "SU1-L3-P0")
        spine_name: Hierarchical spine switch name (e.g., "SU1-S5-P0")
    """
    uplink_port: int
    spine_id: int
    spine_port: int
    plane_id: int
    leaf_name: str
    spine_name: str


@dataclass
class DownlinkConnection:
    """Represents a spine switch downlink connection to a leaf switch.
    
    Attributes:
        downlink_port: Physical downlink port number on the spine switch (0-indexed)
        leaf_id: Target leaf switch ID (0 to L-1)
        leaf_port: Uplink port number on the leaf switch (0-indexed)
        plane_id: Plane/rail this connection belongs to (0 to P-1)
        spine_name: Hierarchical spine switch name (e.g., "SU1-S5-P0")
        leaf_name: Hierarchical leaf switch name (e.g., "SU1-L3-P0")
    """
    downlink_port: int
    leaf_id: int
    leaf_port: int
    plane_id: int
    spine_name: str
    leaf_name: str


class LeafToSpineMapper:
    """Maps leaf switch uplinks to spine switch downlinks deterministically.
    
    This class encapsulates the "full mesh within plane" topology logic,
    ensuring every leaf can reach every spine within its plane with predictable
    port assignments.
    
    **Mapping Algorithm:**
    For a leaf with ID `l` in plane `p`:
      - Has L uplink ports (uplink_port = 0 to L-1)
      - Uplink port `u` connects to:
        * Spine ID: `u` (in same plane `p`)
        * Spine downlink port: `l`
    
    **Physical Port Allocation:**
    Leaf switches:
      - Downlink ports (1 to D): GPU servers (D = S × R ÷ L)
      - Uplink ports (D+1 to D+Spines): Spine switches
      
    Spine switches:
      - Downlink ports (1 to L): Leaf switches
      - Uplink ports (L+1 to L+U): Super-Spine switches (future)
    
    **Symmetry Invariant:**
    If Leaf L connects to Spine S via uplink port U,
    then Spine S connects to Leaf L via downlink port L.
    
    Attributes:
        topology: ClusterTopology defining the fabric geometry
        downlinks_per_leaf: Number of GPU-facing ports on each leaf
        first_uplink_port: First physical port number for uplinks (1-indexed)
    """
    
    def __init__(self, topology: ClusterTopology):
        """Initialize mapper with cluster topology.
        
        Args:
            topology: ClusterTopology instance defining L, P, Spines_per_plane, SU_ID
            
        Raises:
            ValueError: If topology is invalid for spine mapping
        """
        self.topology = topology
        
        # Calculate physical port allocation
        # Leaf downlink ports: 1 to downlinks_per_leaf (GPU servers)
        # Leaf uplink ports: first_uplink_port to first_uplink_port + Spines_per_plane - 1 (Spines)
        self.downlinks_per_leaf = (topology.S * topology.R) // topology.L
        self.first_uplink_port = self.downlinks_per_leaf + 1  # 1-indexed
        
        # Validate topology for spine mapping
        if topology.Spines_per_plane != topology.L:
            print(
                f"⚠️ Warning: Non-standard topology detected. "
                f"Spines_per_plane ({topology.Spines_per_plane}) != "
                f"Leafs_per_plane ({topology.L}). "
                f"This creates oversubscription in the spine layer."
            )
        
        print("📊 LeafToSpineMapper Port Allocation:")
        print(f"   Leaf downlink ports (GPUs): 1-{self.downlinks_per_leaf}")
        print(f"   Leaf uplink ports (Spines): {self.first_uplink_port}-{self.first_uplink_port + topology.Spines_per_plane - 1}")
        print(f"   Spine downlink ports (Leafs): 1-{topology.L}")
    
    def get_physical_uplink_port(self, logical_uplink_id: int) -> int:
        """Convert logical uplink ID to physical port number.
        
        Args:
            logical_uplink_id: Logical uplink index (0 to Spines_per_plane-1)
            
        Returns:
            Physical port number (1-indexed)
            
        Example:
            For a topology with 128 downlink ports:
            >>> mapper.get_physical_uplink_port(0)  # First uplink
            129
            >>> mapper.get_physical_uplink_port(5)  # Sixth uplink
            134
        """
        return self.first_uplink_port + logical_uplink_id
    
    def get_physical_spine_downlink_port(self, leaf_id: int) -> int:
        """Convert leaf ID to physical downlink port on spine.
        
        Args:
            leaf_id: Leaf switch ID (0 to L-1)
            
        Returns:
            Physical port number on spine (1-indexed)
            
        Example:
            >>> mapper.get_physical_spine_downlink_port(3)  # Leaf 3
            4  # Port 4 on spine (1-indexed: Leaf 0→Port 1, Leaf 3→Port 4)
        """
        return leaf_id + 1  # Convert 0-indexed to 1-indexed
    
    def get_leaf_name(self, leaf_id: int, plane_id: int) -> str:
        """Generate hierarchical leaf switch name.
        
        Args:
            leaf_id: Leaf switch ID (0 to L-1)
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            Hierarchical name (e.g., "SU1-L3-P0")
            
        Example:
            >>> mapper.get_leaf_name(3, 0)
            "SU1-L3-P0"
        """
        return f"SU{self.topology.SU_ID}-L{leaf_id}-P{plane_id}"
    
    def get_spine_name(self, spine_id: int, plane_id: int) -> str:
        """Generate hierarchical spine switch name.
        
        Args:
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            Hierarchical name (e.g., "SU1-S5-P0")
            
        Example:
            >>> mapper.get_spine_name(5, 0)
            "SU1-S5-P0"
        """
        return f"SU{self.topology.SU_ID}-S{spine_id}-P{plane_id}"
    
    def get_uplink_mapping(
        self,
        leaf_id: int,
        plane_id: int
    ) -> List[UplinkConnection]:
        """Get all uplink connections for a specific leaf switch.
        
        Returns the full mesh of uplink connections from this leaf to all
        spines in the same plane.
        
        Args:
            leaf_id: Leaf switch ID (0 to L-1)
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            List of UplinkConnection objects, one per uplink port
            
        Raises:
            ValueError: If leaf_id or plane_id is out of bounds
            
        Example:
            >>> mapper.get_uplink_mapping(leaf_id=3, plane_id=0)
            [
                UplinkConnection(uplink_port=0, spine_id=0, spine_port=3, ...),
                UplinkConnection(uplink_port=1, spine_id=1, spine_port=3, ...),
                ...
            ]
        """
        # Validate inputs
        if not (0 <= leaf_id < self.topology.L):
            raise ValueError(
                f"leaf_id ({leaf_id}) out of bounds. "
                f"Must be 0 to {self.topology.L - 1}."
            )
        
        if not (0 <= plane_id < self.topology.P):
            raise ValueError(
                f"plane_id ({plane_id}) out of bounds. "
                f"Must be 0 to {self.topology.P - 1}."
            )
        
        # Generate uplink mappings
        uplinks = []
        leaf_name = self.get_leaf_name(leaf_id, plane_id)
        
        for uplink_port in range(self.topology.Spines_per_plane):
            # Full mesh: uplink port U connects to spine U
            spine_id = uplink_port
            spine_port = leaf_id  # Spine's downlink port equals the leaf ID
            spine_name = self.get_spine_name(spine_id, plane_id)
            
            uplinks.append(UplinkConnection(
                uplink_port=uplink_port,
                spine_id=spine_id,
                spine_port=spine_port,
                plane_id=plane_id,
                leaf_name=leaf_name,
                spine_name=spine_name
            ))
        
        return uplinks
    
    def get_spine_downlinks(
        self,
        spine_id: int,
        plane_id: int
    ) -> List[DownlinkConnection]:
        """Get all downlink connections for a specific spine switch.
        
        Returns the full mesh of downlink connections from this spine to all
        leafs in the same plane.
        
        Args:
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            List of DownlinkConnection objects, one per downlink port
            
        Raises:
            ValueError: If spine_id or plane_id is out of bounds
            
        Example:
            >>> mapper.get_spine_downlinks(spine_id=5, plane_id=0)
            [
                DownlinkConnection(downlink_port=0, leaf_id=0, leaf_port=5, ...),
                DownlinkConnection(downlink_port=1, leaf_id=1, leaf_port=5, ...),
                ...
            ]
        """
        # Validate inputs
        if not (0 <= spine_id < self.topology.Spines_per_plane):
            raise ValueError(
                f"spine_id ({spine_id}) out of bounds. "
                f"Must be 0 to {self.topology.Spines_per_plane - 1}."
            )
        
        if not (0 <= plane_id < self.topology.P):
            raise ValueError(
                f"plane_id ({plane_id}) out of bounds. "
                f"Must be 0 to {self.topology.P - 1}."
            )
        
        # Generate downlink mappings
        downlinks = []
        spine_name = self.get_spine_name(spine_id, plane_id)
        
        for downlink_port in range(self.topology.L):
            # Full mesh: downlink port D connects to leaf D
            leaf_id = downlink_port
            leaf_port = spine_id  # Leaf's uplink port equals the spine ID
            leaf_name = self.get_leaf_name(leaf_id, plane_id)
            
            downlinks.append(DownlinkConnection(
                downlink_port=downlink_port,
                leaf_id=leaf_id,
                leaf_port=leaf_port,
                plane_id=plane_id,
                spine_name=spine_name,
                leaf_name=leaf_name
            ))
        
        return downlinks
    
    def validate_port_mapping(self) -> bool:
        """Validate that the port mapping is symmetric and collision-free.
        
        Checks:
        1. Every leaf uplink port connects to exactly one spine
        2. Every spine downlink port connects to exactly one leaf
        3. Symmetry: If Leaf L → Spine S, then Spine S → Leaf L
        
        Returns:
            True if validation passes
            
        Raises:
            ValueError: If validation fails with detailed error message
        """
        print("🔍 Validating Leaf↔Spine port mapping...")
        
        for plane_id in range(self.topology.P):
            # Check all leafs in this plane
            for leaf_id in range(self.topology.L):
                uplinks = self.get_uplink_mapping(leaf_id, plane_id)
                
                # Verify uplink count
                if len(uplinks) != self.topology.Spines_per_plane:
                    raise ValueError(
                        f"Leaf {leaf_id} in plane {plane_id} has {len(uplinks)} uplinks, "
                        f"expected {self.topology.Spines_per_plane}"
                    )
                
                # Check for port collisions
                used_ports = set()
                for uplink in uplinks:
                    if uplink.uplink_port in used_ports:
                        raise ValueError(
                            f"Port collision: Leaf {leaf_id} plane {plane_id} "
                            f"uses uplink port {uplink.uplink_port} multiple times"
                        )
                    used_ports.add(uplink.uplink_port)
            
            # Check all spines in this plane
            for spine_id in range(self.topology.Spines_per_plane):
                downlinks = self.get_spine_downlinks(spine_id, plane_id)
                
                # Verify downlink count
                if len(downlinks) != self.topology.L:
                    raise ValueError(
                        f"Spine {spine_id} in plane {plane_id} has {len(downlinks)} downlinks, "
                        f"expected {self.topology.L}"
                    )
                
                # Check for port collisions
                used_ports = set()
                for downlink in downlinks:
                    if downlink.downlink_port in used_ports:
                        raise ValueError(
                            f"Port collision: Spine {spine_id} plane {plane_id} "
                            f"uses downlink port {downlink.downlink_port} multiple times"
                        )
                    used_ports.add(downlink.downlink_port)
        
        # Verify symmetry
        for plane_id in range(self.topology.P):
            for leaf_id in range(self.topology.L):
                uplinks = self.get_uplink_mapping(leaf_id, plane_id)
                for uplink in uplinks:
                    # Get the corresponding spine's downlinks
                    spine_downlinks = self.get_spine_downlinks(
                        uplink.spine_id,
                        plane_id
                    )
                    
                    # Find the downlink that should point back to this leaf
                    matching_downlink = None
                    for downlink in spine_downlinks:
                        if downlink.leaf_id == leaf_id:
                            matching_downlink = downlink
                            break
                    
                    if not matching_downlink:
                        raise ValueError(
                            f"Symmetry violation: Leaf {leaf_id} → Spine {uplink.spine_id}, "
                            f"but Spine {uplink.spine_id} doesn't connect back to Leaf {leaf_id}"
                        )
                    
                    # Verify port numbers match
                    if matching_downlink.downlink_port != leaf_id:
                        raise ValueError(
                            f"Port mismatch: Leaf {leaf_id} expects to be on "
                            f"Spine {uplink.spine_id} port {leaf_id}, "
                            f"but found on port {matching_downlink.downlink_port}"
                        )
        
        print("✅ Port mapping validation passed")
        print(f"   Validated {self.topology.P} planes")
        print(f"   Validated {self.topology.L} leafs per plane")
        print(f"   Validated {self.topology.Spines_per_plane} spines per plane")
        print(f"   Total connections: {self.topology.L * self.topology.Spines_per_plane * self.topology.P}")
        
        return True
