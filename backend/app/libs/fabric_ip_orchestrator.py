"""Fabric IP Orchestrator - Deterministic P2P IP Allocation for Leaf↔Spine Links

This module implements the Infrastructure IP allocation layer for NVIDIA DGX SuperPOD
fabric interconnects. It assigns /31 point-to-point subnets to every Leaf↔Spine
link using a deterministic formula that enables reverse lookup during troubleshooting.

**IP Schema Segregation:**
- **GPU Traffic IPs**: 100.{126+P}.x.x (Plane 0: 100.126.x.x, Plane 1: 100.127.x.x)
- **Fabric Infrastructure IPs**: 100.{130+P}.x.x (Plane 0: 100.130.x.x, Plane 1: 100.131.x.x)

This separation ensures:
- Clean BGP peering configuration
- Simplified traceroute analysis
- No IP collision between data plane and control plane

**Deterministic IP Formula:**
For a Leaf↔Spine link in SU `s`, Plane `p`, Link Index `i`:
```
Base Subnet: 100.(130 + p).s.(i * 2)/31
Leaf IP:     100.(130 + p).s.(i * 2)
Spine IP:    100.(130 + p).s.(i * 2 + 1)
```

**Link Index Calculation:**
Link Index = (Leaf_ID * Spines_per_plane) + Spine_ID

This creates a unique, deterministic index for each link in the fabric.

**Example (SU1, Plane 0, Leaf 3 ↔ Spine 5):**
```
Link Index = (3 * 8) + 5 = 29
Subnet: 100.130.1.58/31
Leaf IP: 100.130.1.58 (SU1-L3-P0)
Spine IP: 100.130.1.59 (SU1-S5-P0)
```

**Reverse Lookup:**
Given an IP like 100.130.1.58, the system can decode:
- Plane: 0 (from 130)
- SU: 1 (from third octet)
- Link Index: 29 (from fourth octet ÷ 2)
- Leaf: 3 (Link Index ÷ Spines_per_plane)
- Spine: 5 (Link Index % Spines_per_plane)

**Usage:**
```python
from app.libs.cluster_topology import ClusterTopology
from app.libs.leaf_to_spine_mapper import LeafToSpineMapper
from app.libs.fabric_ip_orchestrator import FabricIPOrchestrator

topology = ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8, SU_ID=1)
mapper = LeafToSpineMapper(topology)
orchestrator = FabricIPOrchestrator(topology, mapper)

# Get IP allocation for a specific link
allocation = orchestrator.get_link_ips(leaf_id=3, spine_id=5, plane_id=0)
print(f"Leaf IP: {allocation.leaf_ip}")
print(f"Spine IP: {allocation.spine_ip}")
print(f"Subnet: {allocation.subnet}")

# Reverse lookup from IP
link_info = orchestrator.reverse_lookup("100.130.1.58")
print(f"This IP belongs to {link_info.leaf_name} ↔ {link_info.spine_name}")
```
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
import ipaddress
from app.libs.cluster_topology import ClusterTopology
from app.libs.leaf_to_spine_mapper import LeafToSpineMapper


@dataclass
class FabricLinkIP:
    """IP allocation for a single Leaf↔Spine link.
    
    Attributes:
        leaf_name: Hierarchical leaf switch name (e.g., "SU1-L3-P0")
        spine_name: Hierarchical spine switch name (e.g., "SU1-S5-P0")
        leaf_id: Leaf switch ID (0 to L-1)
        spine_id: Spine switch ID (0 to Spines_per_plane-1)
        plane_id: Plane ID (0 to P-1)
        su_id: Scalable Unit ID
        link_index: Unique link index within SU and plane
        subnet: /31 subnet in CIDR notation (e.g., "100.130.1.58/31")
        leaf_ip: IP address assigned to leaf interface
        spine_ip: IP address assigned to spine interface
        leaf_port: Physical port number on leaf switch
        spine_port: Physical port number on spine switch
    """
    leaf_name: str
    spine_name: str
    leaf_id: int
    spine_id: int
    plane_id: int
    su_id: int
    link_index: int
    subnet: str
    leaf_ip: str
    spine_ip: str
    leaf_port: int
    spine_port: int


@dataclass
class ReverseLookupResult:
    """Result of reverse IP lookup.
    
    Attributes:
        ip: The queried IP address
        is_fabric_ip: Whether this IP belongs to fabric infrastructure range
        plane_id: Plane ID (None if not fabric IP)
        su_id: Scalable Unit ID (None if not fabric IP)
        link_index: Link index (None if not fabric IP)
        leaf_id: Leaf switch ID (None if not fabric IP)
        spine_id: Spine switch ID (None if not fabric IP)
        leaf_name: Hierarchical leaf name (None if not fabric IP)
        spine_name: Hierarchical spine name (None if not fabric IP)
        is_leaf_side: True if IP is on leaf side, False if on spine side
        peer_ip: IP address of the peer device
    """
    ip: str
    is_fabric_ip: bool
    plane_id: Optional[int] = None
    su_id: Optional[int] = None
    link_index: Optional[int] = None
    leaf_id: Optional[int] = None
    spine_id: Optional[int] = None
    leaf_name: Optional[str] = None
    spine_name: Optional[str] = None
    is_leaf_side: Optional[bool] = None
    peer_ip: Optional[str] = None


class FabricIPOrchestrator:
    """Orchestrates IP allocation for Leaf↔Spine fabric links.
    
    This orchestrator implements the deterministic IP allocation scheme
    for fabric infrastructure, ensuring:
    - No IP collisions within or across SUs
    - Deterministic reverse lookup from IP to physical link
    - Clean separation from GPU traffic IPs
    
    **IP Range Allocation:**
    - Plane 0 Fabric: 100.130.0.0/16
    - Plane 1 Fabric: 100.131.0.0/16
    - Each SU gets: 100.{130+P}.{SU_ID}.0/24
    - Each link gets: /31 subnet (2 IPs)
    
    **Scalability:**
    - Max links per SU per plane: 128 (256 IPs / 2)
    - Max SUs per deployment: 255
    - Total fabric IPs per plane: ~65K
    """
    
    # Base IP ranges for fabric infrastructure
    FABRIC_BASE_PLANE_0 = "100.130.0.0"  # Plane 0 fabric IPs
    FABRIC_BASE_PLANE_1 = "100.131.0.0"  # Plane 1 fabric IPs
    
    def __init__(self, topology: ClusterTopology, mapper: LeafToSpineMapper):
        """Initialize orchestrator with topology and mapper.
        
        Args:
            topology: ClusterTopology defining the fabric
            mapper: LeafToSpineMapper for port mappings
        """
        self.topology = topology
        self.mapper = mapper
        
        # Validate that we won't exceed IP space
        max_links_per_plane = topology.L * topology.Spines_per_plane
        max_ips_needed = max_links_per_plane * 2  # /31 subnets
        
        if max_ips_needed > 256:
            raise ValueError(
                f"Topology requires {max_ips_needed} IPs per SU per plane, "
                f"but only 256 available in /24 subnet. "
                f"Consider using /23 or larger subnet."
            )
        
        print("🌐 FabricIPOrchestrator initialized:")
        print(f"   Fabric IP base (Plane 0): {self.FABRIC_BASE_PLANE_0}")
        print(f"   Fabric IP base (Plane 1): {self.FABRIC_BASE_PLANE_1}")
        print(f"   Links per plane: {max_links_per_plane}")
        print(f"   IPs per SU per plane: {max_ips_needed}")
        print(f"   IP utilization: {(max_ips_needed / 256) * 100:.1f}% of /24 subnet")
    
    def _calculate_link_index(self, leaf_id: int, spine_id: int) -> int:
        """Calculate unique link index for a Leaf↔Spine connection.
        
        Args:
            leaf_id: Leaf switch ID (0 to L-1)
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            
        Returns:
            Unique link index within the SU and plane
            
        Example:
            >>> orchestrator._calculate_link_index(3, 5)  # L=8, Spines=8
            29  # (3 * 8) + 5
        """
        return (leaf_id * self.topology.Spines_per_plane) + spine_id
    
    def _decode_link_index(self, link_index: int) -> tuple[int, int]:
        """Decode link index back to leaf_id and spine_id.
        
        Args:
            link_index: Link index to decode
            
        Returns:
            Tuple of (leaf_id, spine_id)
            
        Example:
            >>> orchestrator._decode_link_index(29)  # L=8, Spines=8
            (3, 5)
        """
        leaf_id = link_index // self.topology.Spines_per_plane
        spine_id = link_index % self.topology.Spines_per_plane
        return (leaf_id, spine_id)
    
    def get_link_ips(
        self,
        leaf_id: int,
        spine_id: int,
        plane_id: int
    ) -> FabricLinkIP:
        """Get IP allocation for a specific Leaf↔Spine link.
        
        Args:
            leaf_id: Leaf switch ID (0 to L-1)
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            FabricLinkIP with complete IP allocation details
            
        Raises:
            ValueError: If IDs are out of bounds
            
        Example:
            >>> allocation = orchestrator.get_link_ips(3, 5, 0)
            >>> print(allocation.subnet)
            "100.130.1.58/31"
            >>> print(allocation.leaf_ip)
            "100.130.1.58"
            >>> print(allocation.spine_ip)
            "100.130.1.59"
        """
        # Validation
        if not (0 <= leaf_id < self.topology.L):
            raise ValueError(f"Leaf ID {leaf_id} out of bounds (0 to {self.topology.L - 1})")
        
        if not (0 <= spine_id < self.topology.Spines_per_plane):
            raise ValueError(
                f"Spine ID {spine_id} out of bounds (0 to {self.topology.Spines_per_plane - 1})"
            )
        
        if not (0 <= plane_id < self.topology.P):
            raise ValueError(f"Plane ID {plane_id} out of bounds (0 to {self.topology.P - 1})")
        
        # Calculate link index
        link_index = self._calculate_link_index(leaf_id, spine_id)
        
        # Build IP: 100.(130 + plane_id).su_id.(link_index * 2)
        second_octet = 130 + plane_id
        third_octet = self.topology.SU_ID
        fourth_octet_base = link_index * 2
        
        leaf_ip = f"100.{second_octet}.{third_octet}.{fourth_octet_base}"
        spine_ip = f"100.{second_octet}.{third_octet}.{fourth_octet_base + 1}"
        subnet = f"{leaf_ip}/31"
        
        # Get switch names and port numbers
        leaf_name = self.mapper.get_leaf_name(leaf_id, plane_id)
        spine_name = self.mapper.get_spine_name(spine_id, plane_id)
        leaf_port = self.mapper.get_physical_uplink_port(spine_id)
        spine_port = self.mapper.get_physical_spine_downlink_port(leaf_id)
        
        return FabricLinkIP(
            leaf_name=leaf_name,
            spine_name=spine_name,
            leaf_id=leaf_id,
            spine_id=spine_id,
            plane_id=plane_id,
            su_id=self.topology.SU_ID,
            link_index=link_index,
            subnet=subnet,
            leaf_ip=leaf_ip,
            spine_ip=spine_ip,
            leaf_port=leaf_port,
            spine_port=spine_port
        )
    
    def get_all_fabric_ips(self) -> List[FabricLinkIP]:
        """Generate IP allocations for ALL Leaf↔Spine links in this SU.
        
        Returns:
            List of FabricLinkIP objects, one per link
            
        Example:
            >>> allocations = orchestrator.get_all_fabric_ips()
            >>> print(f"Total links: {len(allocations)}")
            Total links: 128  # (8 leafs * 8 spines * 2 planes)
        """
        allocations = []
        
        for plane_id in range(self.topology.P):
            for leaf_id in range(self.topology.L):
                for spine_id in range(self.topology.Spines_per_plane):
                    allocation = self.get_link_ips(leaf_id, spine_id, plane_id)
                    allocations.append(allocation)
        
        return allocations
    
    def reverse_lookup(self, ip: str) -> ReverseLookupResult:
        """Reverse lookup: decode IP address to physical link information.
        
        This is critical for troubleshooting. Given an IP from a traceroute
        or BGP session error, the operator can identify the exact physical
        cable and port.
        
        Args:
            ip: IP address to look up (e.g., "100.130.1.58")
            
        Returns:
            ReverseLookupResult with decoded link information
            
        Example:
            >>> result = orchestrator.reverse_lookup("100.130.1.58")
            >>> print(f"{result.leaf_name} port {result.leaf_port} ↔ {result.spine_name} port {result.spine_port}")
            SU1-L3-P0 port 22 ↔ SU1-S5-P0 port 4
        """
        try:
            ip_obj = ipaddress.IPv4Address(ip)
            octets = str(ip_obj).split('.')
            
            # Check if this is a fabric IP (100.130.x.x or 100.131.x.x)
            if octets[0] != '100' or octets[1] not in ['130', '131']:
                return ReverseLookupResult(
                    ip=ip,
                    is_fabric_ip=False
                )
            
            # Decode plane_id from second octet
            plane_id = int(octets[1]) - 130  # 130→0, 131→1
            
            # Decode SU_ID from third octet
            su_id = int(octets[2])
            
            # Decode link_index from fourth octet
            fourth_octet = int(octets[3])
            is_leaf_side = (fourth_octet % 2 == 0)  # Even = leaf, odd = spine
            link_index = fourth_octet // 2
            
            # Decode leaf_id and spine_id
            leaf_id, spine_id = self._decode_link_index(link_index)
            
            # Validate decoded values
            if plane_id >= self.topology.P:
                return ReverseLookupResult(
                    ip=ip,
                    is_fabric_ip=True,
                    plane_id=plane_id,
                    su_id=su_id
                )
            
            if leaf_id >= self.topology.L or spine_id >= self.topology.Spines_per_plane:
                return ReverseLookupResult(
                    ip=ip,
                    is_fabric_ip=True,
                    plane_id=plane_id,
                    su_id=su_id,
                    link_index=link_index
                )
            
            # Generate names
            leaf_name = self.mapper.get_leaf_name(leaf_id, plane_id)
            spine_name = self.mapper.get_spine_name(spine_id, plane_id)
            
            # Calculate peer IP
            peer_ip = f"100.{octets[1]}.{octets[2]}.{fourth_octet + (1 if is_leaf_side else -1)}"
            
            return ReverseLookupResult(
                ip=ip,
                is_fabric_ip=True,
                plane_id=plane_id,
                su_id=su_id,
                link_index=link_index,
                leaf_id=leaf_id,
                spine_id=spine_id,
                leaf_name=leaf_name,
                spine_name=spine_name,
                is_leaf_side=is_leaf_side,
                peer_ip=peer_ip
            )
            
        except Exception as e:
            print(f"⚠️ Error during reverse lookup of {ip}: {e}")
            return ReverseLookupResult(
                ip=ip,
                is_fabric_ip=False
            )
    
    def export_ip_table(self) -> List[Dict]:
        """Export complete IP allocation table for documentation/validation.
        
        Returns:
            List of dictionaries with IP allocation details
            
        Example:
            >>> table = orchestrator.export_ip_table()
            >>> import pandas as pd
            >>> df = pd.DataFrame(table)
            >>> df.to_csv('fabric_ips.csv', index=False)
        """
        allocations = self.get_all_fabric_ips()
        
        return [
            {
                'SU_ID': alloc.su_id,
                'Plane': alloc.plane_id,
                'Leaf_Name': alloc.leaf_name,
                'Leaf_Port': alloc.leaf_port,
                'Leaf_IP': alloc.leaf_ip,
                'Spine_Name': alloc.spine_name,
                'Spine_Port': alloc.spine_port,
                'Spine_IP': alloc.spine_ip,
                'Subnet': alloc.subnet,
                'Link_Index': alloc.link_index
            }
            for alloc in allocations
        ]
    
    def validate_no_ip_collisions(self) -> bool:
        """Validate that there are no IP collisions in the allocation.
        
        Returns:
            True if no collisions detected
            
        Raises:
            ValueError: If collisions are detected
        """
        print("🔍 Validating fabric IP allocations for collisions...")
        
        allocations = self.get_all_fabric_ips()
        seen_ips = set()
        collisions = []
        
        for alloc in allocations:
            for ip in [alloc.leaf_ip, alloc.spine_ip]:
                if ip in seen_ips:
                    collisions.append(ip)
                seen_ips.add(ip)
        
        if collisions:
            raise ValueError(
                f"IP collisions detected: {collisions}\n"
                f"This indicates a bug in the allocation algorithm."
            )
        
        print("✅ No IP collisions detected")
        print(f"   Allocated {len(seen_ips)} unique IPs")
        print(f"   Across {len(allocations)} links")
        print(f"   In {self.topology.P} planes")
        
        return True
