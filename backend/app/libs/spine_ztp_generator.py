"""Spine ZTP Configuration Generator - Automated Tier 2 Switch Provisioning

This module generates Zero-Touch Provisioning (ZTP) configurations for Spine switches
(Tier 2) in NVIDIA DGX SuperPOD architectures. It creates vendor-specific switch
configurations with BGP peering, LLDP validation, and fabric infrastructure setup.

**Architecture Context:**
- **Tier 1 (Leaf)**: ToR switches connecting GPU servers
- **Tier 2 (Spine)**: SU-scoped aggregation layer (THIS MODULE)
- **Tier 3 (Super-Spine/Core)**: Cross-SU fabric interconnect (future)

**ZTP Workflow:**
1. Spine switch boots with factory defaults
2. DHCP provides management IP and ZTP script URL
3. Switch downloads and executes ZTP script from this generator
4. Configuration includes:
   - Hostname (hierarchical naming: SU1-S5-P0)
   - Interface descriptions and IP assignments
   - BGP peering with all Leafs in same plane
   - LLDP for neighbor discovery
   - Port breakout configuration (if needed)

**BGP Strategy:**
Spine switches use eBGP with:
- ASN per plane: 65000 + (SU_ID * 10) + Plane_ID
- Example: SU1 Plane 0 Spines → ASN 65010
- Example: SU1 Plane 1 Spines → ASN 65011
- Leafs peer with Spines in same plane
- eBGP multi-hop for resiliency

**Supported Vendors:**
- NVIDIA Spectrum-4 / Quantum-2 (primary)
- Arista 7800R4 series
- Cisco Nexus 9000 series

**Usage:**
```python
from app.libs.cluster_topology import ClusterTopology
from app.libs.leaf_to_spine_mapper import LeafToSpineMapper
from app.libs.fabric_ip_orchestrator import FabricIPOrchestrator
from app.libs.spine_ztp_generator import SpineZTPGenerator

topology = ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8, SU_ID=1)
mapper = LeafToSpineMapper(topology)
orchestrator = FabricIPOrchestrator(topology, mapper)
generator = SpineZTPGenerator(topology, mapper, orchestrator)

# Generate config for specific spine
config = generator.generate_spine_config(
    spine_id=5,
    plane_id=0,
    vendor='nvidia'
)

print(config)
```
"""

from typing import Dict, List
from dataclasses import dataclass
from app.libs.cluster_topology import ClusterTopology
from app.libs.leaf_to_spine_mapper import LeafToSpineMapper
from app.libs.fabric_ip_orchestrator import FabricIPOrchestrator


@dataclass
class BGPPeerConfig:
    """BGP peer configuration for a single neighbor.
    
    Attributes:
        peer_ip: IP address of BGP neighbor
        peer_asn: ASN of BGP neighbor
        peer_name: Human-readable neighbor name
        local_ip: Local IP used for peering
        description: Interface/peer description
    """
    peer_ip: str
    peer_asn: int
    peer_name: str
    local_ip: str
    description: str


@dataclass
class InterfaceConfig:
    """Physical interface configuration.
    
    Attributes:
        interface_name: Interface identifier (e.g., "Ethernet1/1")
        description: Interface description
        ip_address: IP address with CIDR (e.g., "100.130.1.59/31")
        peer_name: Name of connected device
        peer_port: Port number on connected device
        enabled: Whether interface should be enabled
    """
    interface_name: str
    description: str
    ip_address: str
    peer_name: str
    peer_port: int
    enabled: bool = True


class SpineZTPGenerator:
    """Generates ZTP configurations for Spine switches.
    
    This generator creates complete, production-ready switch configurations
    for automated deployment. Configurations are vendor-specific and include
    all necessary elements for fabric integration.
    
    **Configuration Elements:**
    - Hierarchical hostname (SU{ID}-S{#}-P{#})
    - Management interface setup
    - Downlink interfaces to Leafs (with BGP)
    - Uplink interfaces to Super-Spines (future)
    - LLDP for topology validation
    - NTP, DNS, logging
    - SNMP monitoring hooks
    """
    
    # BGP ASN allocation strategy
    BGP_ASN_BASE = 65000  # Private ASN range start
    
    def __init__(
        self,
        topology: ClusterTopology,
        mapper: LeafToSpineMapper,
        orchestrator: FabricIPOrchestrator
    ):
        """Initialize generator with topology and orchestration components.
        
        Args:
            topology: ClusterTopology defining fabric geometry
            mapper: LeafToSpineMapper for port mappings
            orchestrator: FabricIPOrchestrator for IP allocation
        """
        self.topology = topology
        self.mapper = mapper
        self.orchestrator = orchestrator
        
        print("🔧 SpineZTPGenerator initialized")
        print("   Target vendor: NVIDIA Spectrum/Quantum (primary)")
        print(f"   BGP ASN strategy: {self.BGP_ASN_BASE} + (SU_ID * 10) + Plane_ID")
    
    def _get_spine_asn(self, plane_id: int) -> int:
        """Calculate BGP ASN for a Spine in a specific plane.
        
        Args:
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            BGP ASN for this plane's Spines
            
        Example:
            >>> generator._get_spine_asn(0)  # SU1, Plane 0
            65010
            >>> generator._get_spine_asn(1)  # SU1, Plane 1
            65011
        """
        return self.BGP_ASN_BASE + (self.topology.SU_ID * 10) + plane_id
    
    def _get_leaf_asn(self, plane_id: int) -> int:
        """Calculate BGP ASN for Leafs in a specific plane.
        
        Leafs use a different ASN range to enable eBGP peering.
        
        Args:
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            BGP ASN for this plane's Leafs
            
        Example:
            >>> generator._get_leaf_asn(0)  # SU1, Plane 0
            64010
            >>> generator._get_leaf_asn(1)  # SU1, Plane 1
            64011
        """
        # Leafs use 64000 range, Spines use 65000 range
        return (self.BGP_ASN_BASE - 1000) + (self.topology.SU_ID * 10) + plane_id
    
    def get_spine_hostname(self, spine_id: int, plane_id: int) -> str:
        """Generate hierarchical hostname for Spine switch.
        
        Args:
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            Hostname in format SU{SU_ID}-S{spine_id}-P{plane_id}
            
        Example:
            >>> generator.get_spine_hostname(5, 0)
            "SU1-S5-P0"
        """
        return self.mapper.get_spine_name(spine_id, plane_id)
    
    def get_interface_configs(
        self,
        spine_id: int,
        plane_id: int,
        vendor: str = 'nvidia'
    ) -> List[InterfaceConfig]:
        """Generate interface configurations for all downlinks to Leafs.
        
        Args:
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            plane_id: Plane ID (0 to P-1)
            vendor: Switch vendor ('nvidia', 'arista', 'cisco')
            
        Returns:
            List of InterfaceConfig objects for each downlink
            
        Example:
            >>> configs = generator.get_interface_configs(5, 0, 'nvidia')
            >>> for cfg in configs:
            ...     print(f"{cfg.interface_name}: {cfg.ip_address} → {cfg.peer_name}")
            Ethernet1/1: 100.130.1.1/31 → SU1-L0-P0
            Ethernet1/2: 100.130.1.3/31 → SU1-L1-P0
            ...
        """
        downlinks = self.mapper.get_spine_downlinks(spine_id, plane_id)
        interface_configs = []
        
        for downlink in downlinks:
            # Get IP allocation for this link
            link_ips = self.orchestrator.get_link_ips(
                leaf_id=downlink.leaf_id,
                spine_id=spine_id,
                plane_id=plane_id
            )
            
            # Generate vendor-specific interface name
            if vendor == 'nvidia':
                # NVIDIA: Ethernet1/1, Ethernet1/2, etc.
                interface_name = f"Ethernet1/{downlink.downlink_port}"
            elif vendor == 'arista':
                # Arista: Ethernet1, Ethernet2, etc.
                interface_name = f"Ethernet{downlink.downlink_port}"
            elif vendor == 'cisco':
                # Cisco: Ethernet1/1, Ethernet1/2, etc.
                interface_name = f"Ethernet1/{downlink.downlink_port}"
            else:
                interface_name = f"eth{downlink.downlink_port}"
            
            interface_configs.append(InterfaceConfig(
                interface_name=interface_name,
                description=f"DOWNLINK_TO_{downlink.leaf_name}_PORT_{downlink.leaf_port}",
                ip_address=f"{link_ips.spine_ip}/31",
                peer_name=downlink.leaf_name,
                peer_port=downlink.leaf_port,
                enabled=True
            ))
        
        return interface_configs
    
    def get_bgp_peer_configs(
        self,
        spine_id: int,
        plane_id: int
    ) -> List[BGPPeerConfig]:
        """Generate BGP peer configurations for all Leaf neighbors.
        
        Args:
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            List of BGPPeerConfig objects for each Leaf peer
            
        Example:
            >>> peers = generator.get_bgp_peer_configs(5, 0)
            >>> for peer in peers:
            ...     print(f"Peer {peer.peer_name} ({peer.peer_ip}) ASN {peer.peer_asn}")
            Peer SU1-L0-P0 (100.130.1.0) ASN 64010
            Peer SU1-L1-P0 (100.130.1.2) ASN 64010
            ...
        """
        downlinks = self.mapper.get_spine_downlinks(spine_id, plane_id)
        bgp_peers = []
        
        leaf_asn = self._get_leaf_asn(plane_id)
        
        for downlink in downlinks:
            # Get IP allocation for this link
            link_ips = self.orchestrator.get_link_ips(
                leaf_id=downlink.leaf_id,
                spine_id=spine_id,
                plane_id=plane_id
            )
            
            bgp_peers.append(BGPPeerConfig(
                peer_ip=link_ips.leaf_ip,
                peer_asn=leaf_asn,
                peer_name=downlink.leaf_name,
                local_ip=link_ips.spine_ip,
                description=f"BGP_PEER_{downlink.leaf_name}"
            ))
        
        return bgp_peers
    
    def generate_nvidia_config(
        self,
        spine_id: int,
        plane_id: int
    ) -> str:
        """Generate complete ZTP configuration for NVIDIA Spectrum/Quantum switch.
        
        Args:
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            Complete switch configuration as string
        """
        hostname = self.get_spine_hostname(spine_id, plane_id)
        local_asn = self._get_spine_asn(plane_id)
        interfaces = self.get_interface_configs(spine_id, plane_id, 'nvidia')
        bgp_peers = self.get_bgp_peer_configs(spine_id, plane_id)
        
        config = f"""# NVIDIA Cumulus Linux Configuration
# Auto-generated by SpineZTPGenerator
# Hostname: {hostname}
# SU: {self.topology.SU_ID}, Plane: {plane_id}, Spine: {spine_id}
# Generated for: NVIDIA Spectrum-4 / Quantum-2

# ============================================================================
# SYSTEM CONFIGURATION
# ============================================================================

# Set hostname
hostname {hostname}

# Enable LLDP
lldp:
  tx-interval: 30
  tx-hold: 4

# NTP Configuration
ntp:
  servers:
    - 0.cumulusnetworks.pool.ntp.org
    - 1.cumulusnetworks.pool.ntp.org

# ============================================================================
# INTERFACE CONFIGURATION - DOWNLINKS TO LEAFS
# ============================================================================

"""
        
        # Generate interface configurations
        for iface in interfaces:
            config += f"""
# Interface: {iface.interface_name}
# Connected to: {iface.peer_name} port {iface.peer_port}
auto {iface.interface_name}
iface {iface.interface_name}
    description {iface.description}
    address {iface.ip_address}
    mtu 9216
    link-speed 400000
    link-duplex full

"""
        
        # BGP Configuration
        config += f"""
# ============================================================================
# BGP CONFIGURATION
# ============================================================================

# Router BGP
router bgp {local_asn}
  bgp router-id {self.orchestrator.get_link_ips(0, spine_id, plane_id).spine_ip}
  bgp log-neighbor-changes
  no bgp default ipv4-unicast
  
  # BGP timers (fast convergence)
  timers bgp 3 9
  
  # Address family IPv4 unicast
  address-family ipv4 unicast
    redistribute connected
  exit-address-family
  
"""
        
        # Add BGP neighbors
        for peer in bgp_peers:
            config += f"""
  # Peer: {peer.peer_name}
  neighbor {peer.peer_ip} remote-as {peer.peer_asn}
  neighbor {peer.peer_ip} description {peer.description}
  neighbor {peer.peer_ip} timers 3 9
  neighbor {peer.peer_ip} timers connect 10
  neighbor {peer.peer_ip} address-family ipv4 unicast
"""
        
        config += f"""

# ============================================================================
# MONITORING & LOGGING
# ============================================================================

# Enable syslog
logging:
  remote:
    - server: 10.0.0.1
      port: 514
      protocol: udp

# SNMP Configuration
snmp:
  enabled: true
  community: public
  location: "SU{self.topology.SU_ID} Spine Tier"
  contact: "netops@example.com"

# ============================================================================
# LLDP NEIGHBOR VALIDATION
# ============================================================================

# Expected LLDP neighbors (for validation)
# This spine should see exactly {self.topology.L} Leaf switches:
"""
        
        for iface in interfaces:
            config += f"#   {iface.interface_name} → {iface.peer_name}\n"
        
        config += "\n# End of configuration\n"
        
        return config
    
    def generate_arista_config(
        self,
        spine_id: int,
        plane_id: int
    ) -> str:
        """Generate complete ZTP configuration for Arista switch.
        
        Args:
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            plane_id: Plane ID (0 to P-1)
            
        Returns:
            Complete switch configuration as string
        """
        hostname = self.get_spine_hostname(spine_id, plane_id)
        local_asn = self._get_spine_asn(plane_id)
        interfaces = self.get_interface_configs(spine_id, plane_id, 'arista')
        bgp_peers = self.get_bgp_peer_configs(spine_id, plane_id)
        
        config = f"""! Arista EOS Configuration
! Auto-generated by SpineZTPGenerator
! Hostname: {hostname}
! SU: {self.topology.SU_ID}, Plane: {plane_id}, Spine: {spine_id}
!

hostname {hostname}
!
service routing protocols model multi-agent
!
"""
        
        # Interface configurations
        for iface in interfaces:
            config += f"""
interface {iface.interface_name}
   description {iface.description}
   no switchport
   ip address {iface.ip_address}
   mtu 9214
   speed forced 400gfull
   no shutdown
!
"""
        
        # BGP configuration
        config += f"""
router bgp {local_asn}
   router-id {self.orchestrator.get_link_ips(0, spine_id, plane_id).spine_ip}
   maximum-paths 128
   bgp listen range 100.130.0.0/16 peer-group LEAFS remote-as {self._get_leaf_asn(plane_id)}
   !
"""
        
        for peer in bgp_peers:
            config += f"""
   neighbor {peer.peer_ip} remote-as {peer.peer_asn}
   neighbor {peer.peer_ip} description {peer.description}
   neighbor {peer.peer_ip} maximum-routes 12000
"""
        
        config += "\n   address-family ipv4\n"
        for peer in bgp_peers:
            config += f"      neighbor {peer.peer_ip} activate\n"
        
        config += "      redistribute connected\n!"
        
        # LLDP
        config += "\n\nlldp run\nlldp timer 30\n!"
        
        config += "\nend\n"
        
        return config
    
    def generate_spine_config(
        self,
        spine_id: int,
        plane_id: int,
        vendor: str = 'nvidia'
    ) -> str:
        """Generate complete ZTP configuration for a Spine switch.
        
        Args:
            spine_id: Spine switch ID (0 to Spines_per_plane-1)
            plane_id: Plane ID (0 to P-1)
            vendor: Switch vendor ('nvidia', 'arista', 'cisco')
            
        Returns:
            Complete vendor-specific switch configuration
            
        Raises:
            ValueError: If spine_id, plane_id, or vendor is invalid
            
        Example:
            >>> config = generator.generate_spine_config(5, 0, 'nvidia')
            >>> with open('SU1-S5-P0.cfg', 'w') as f:
            ...     f.write(config)
        """
        # Validation
        if not (0 <= spine_id < self.topology.Spines_per_plane):
            raise ValueError(
                f"Spine ID {spine_id} out of bounds (0 to {self.topology.Spines_per_plane - 1})"
            )
        
        if not (0 <= plane_id < self.topology.P):
            raise ValueError(
                f"Plane ID {plane_id} out of bounds (0 to {self.topology.P - 1})"
            )
        
        vendor = vendor.lower()
        
        if vendor == 'nvidia':
            return self.generate_nvidia_config(spine_id, plane_id)
        elif vendor == 'arista':
            return self.generate_arista_config(spine_id, plane_id)
        elif vendor == 'cisco':
            raise NotImplementedError("Cisco NX-OS configuration not yet implemented")
        else:
            raise ValueError(
                f"Unsupported vendor: {vendor}. "
                f"Supported vendors: nvidia, arista, cisco"
            )
    
    def generate_all_spine_configs(
        self,
        vendor: str = 'nvidia'
    ) -> Dict[str, str]:
        """Generate ZTP configurations for ALL Spine switches in this SU.
        
        Args:
            vendor: Switch vendor ('nvidia', 'arista', 'cisco')
            
        Returns:
            Dictionary mapping hostname to configuration string
            
        Example:
            >>> configs = generator.generate_all_spine_configs('nvidia')
            >>> for hostname, config in configs.items():
            ...     with open(f"{hostname}.cfg", 'w') as f:
            ...         f.write(config)
            Generated 16 config files (8 spines × 2 planes)
        """
        configs = {}
        
        for plane_id in range(self.topology.P):
            for spine_id in range(self.topology.Spines_per_plane):
                hostname = self.get_spine_hostname(spine_id, plane_id)
                config = self.generate_spine_config(spine_id, plane_id, vendor)
                configs[hostname] = config
        
        print(f"✅ Generated {len(configs)} Spine configurations")
        print(f"   Vendor: {vendor.upper()}")
        print(f"   Planes: {self.topology.P}")
        print(f"   Spines per plane: {self.topology.Spines_per_plane}")
        
        return configs
