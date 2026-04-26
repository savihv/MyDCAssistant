"""
JIT ZTP Generator - Dynamic Switch Configuration Script Builder

Generates Zero-Touch Provisioning (ZTP) scripts on-the-fly based on
switch hardware specs and GPU cluster topology.

**CRITICAL ARCHITECTURE CHANGE:**
Ports are no longer configured sequentially (Port 1 → IP 1, Port 2 → IP 2).
Instead, each port is configured to EXPECT a specific GPU based on topology.

This is the "brain" that translates:
1. Cluster topology (G, N, S, R, P, L) → GPU-to-Leaf mappings
2. Hardware specs (port count, interface names) → Switch capabilities
3. IP allocation (GPU-aware /31 subnets) → Port configurations

Into executable configuration scripts that switches download and run.

Example:
    from app.libs.cluster_topology import ClusterTopology
    from app.libs.gpu_to_leaf_mapper import GPUToLeafMapper
    
    topology = ClusterTopology(G=8, N=2, S=16, R=8, P=2, L=8)
    mapper = GPUToLeafMapper(topology)
    generator = JITZTPGenerator(ip_allocator, switch_db)
    
    # Generate config for Leaf 1 in Plane 0
    ztp_script = generator.generate_full_config(
        switch_id="SW-RACK01-LEAF1-P0",
        plane_id=0,
        leaf_id=1,
        vendor="NVIDIA",
        model="QM9700",
        mgmt_ip="10.0.1.250",
        topology=topology,
        mapper=mapper
    )
    # → Configures all 128 ports with expected GPU connections
"""

from typing import Dict, Optional
from datetime import datetime
from app.libs.cluster_topology import ClusterTopology
from app.libs.gpu_to_leaf_mapper import GPUToLeafMapper
from app.libs.ip_schema_orchestrator import IPSchemaOrchestrator


class JITZTPGenerator:
    """Generates ZTP configuration scripts dynamically.
    
    **NEW GPU-Aware Architecture with Global IP Addressing:**
    The generator now supports two modes:
    
    1. GPU-Aware Mode (PREFERRED for InfiniBand fabric):
       - Requires topology, mapper, and ip_orchestrator
       - Each port configured for specific GPU connection
       - Port descriptions: "GPU1-Rack2-Srv5-Tail0"
       - IP allocation using GLOBAL rack IDs (multi-SU aware)
    
    2. Legacy Mode (for management/OOB networks):
       - Simple sequential port configuration
       - Port descriptions: "Port 1", "Port 2", etc.
       - IP allocation based on port number
    
    The generator combines:
    1. Hardware specs (port count, interface naming) from SwitchModelDatabase
    2. Topology (GPU-to-Leaf mappings) from ClusterTopology + GPUToLeafMapper
    3. **NEW: Global IP addresses from IPSchemaOrchestrator (multi-SU aware)**
    4. Switch identity (hostname, role) from Hardware Matrix
    
    Output: Vendor-specific configuration script that:
    - Sets hostname and management IP
    - Configures all data ports with expected GPU connections
    - Adds port descriptions for troubleshooting
    - Enables interfaces
    
    Supported Vendors:
    - NVIDIA/Mellanox (Onyx OS)
    - Arista (EOS)
    - Cisco (NX-OS)
    - Generic (CLI-based configuration)
    """
    
    def __init__(self, switch_db, ip_orchestrator: Optional[IPSchemaOrchestrator] = None):
        """Initialize ZTP generator.
        
        Args:
            switch_db: SwitchModelDatabase instance for hardware specs
            ip_orchestrator: IPSchemaOrchestrator for global IP allocation (multi-SU aware)
                           If None, global IPs cannot be generated (legacy mode only)
        """
        self.switch_db = switch_db
        self.ip_orchestrator = ip_orchestrator
        print("⚙️ JITZTPGenerator initialized")
        if ip_orchestrator:
            print("   Mode: Global IP Schema (Multi-SU aware)")
        else:
            print("   Mode: Legacy (Local IPs only)")
    
    def generate_full_config(
        self,
        switch_id: str,
        plane_id: int,
        leaf_id: int,
        vendor: str,
        model: str,
        mgmt_ip: str,
        topology: ClusterTopology,
        mapper: GPUToLeafMapper,
        fetcher=None
    ) -> Dict:
        """Generate FULL ZTP configuration script for a leaf switch (GPU-aware with global IPs).
        
        **NOW WITH MULTI-SU GLOBAL IP ALLOCATION:**
        Uses IPSchemaOrchestrator.generate_gpu_ip() to assign globally unique IPs
        across all Scalable Units in the cluster.
        
        This is the NEW main entry point for GPU cluster deployments.
        Use this for InfiniBand backend fabric switches.
        
        Args:
            switch_id: Switch identifier (e.g., "SU1-L3-P0")
            plane_id: Plane ID (0-based: 0 for Tail 0, 1 for Tail 1)
            leaf_id: Leaf ID within plane (1-based: 1..L)
            vendor: Vendor name (e.g., "NVIDIA", "Arista")
            model: Model number (e.g., "QM9700", "7060X4")
            mgmt_ip: Management IP assigned via DHCP
            topology: ClusterTopology instance defining network geometry
            mapper: GPUToLeafMapper instance for GPU-to-switch mappings
            fetcher: DatasheetFetcher instance (optional)
            
        Returns:
            Dict with keys:
            - script_content: str (full ZTP script)
            - script_type: str ("bash", "python", "cli")
            - port_count: int (total ports configured)
            - configured_ports: int (ports with GPU connections)
            - vendor: str
            - model: str
            - generated_at: str (ISO timestamp)
            - plane_id: int
            - leaf_id: int
            
        Example:
            >>> result = generator.generate_full_config(
            ...     switch_id="SU1-L3-P0",
            ...     plane_id=0,
            ...     leaf_id=3,
            ...     vendor="NVIDIA",
            ...     model="QM9700",
            ...     mgmt_ip="10.0.1.250",
            ...     topology=topology,
            ...     mapper=mapper
            ... )
            >>> print(result['configured_ports'])
            128  # 8 racks × 16 servers = 128 connections
        """
        print(f"\n⚙️ Generating FULL ZTP config for {switch_id}")
        print(f"   Vendor: {vendor} {model}")
        print(f"   Plane: {plane_id}, Leaf: {leaf_id}")
        print(f"   Management IP: {mgmt_ip}")
        print(f"   Topology: {topology.G} GPUs/server, {topology.L} Leafs/plane")
        print(f"   Multi-SU: SU {topology.SU_ID}/{topology.SU_COUNT}")
        
        # Step 1: Get hardware specs
        specs = self.switch_db.get_or_learn_specs(vendor, model, fetcher)
        physical_port_count = specs['data_port_count']  # Physical OSFP/QSFP connectors
        interface_prefix = specs['interface_prefix']
        os_version = specs['os_version']
        
        # Calculate effective ports after cable split
        effective_ports = topology.calculate_effective_ports(physical_port_count)
        
        print(f"   Physical Ports: {physical_port_count}")
        print(f"   Cable Split: {topology.cable_split}:1")
        print(f"   Effective Ports: {effective_ports}")
        print(f"   Interface Template: {interface_prefix}")
        
        # Step 2: Generate GPU-to-Port mappings with GLOBAL IPs
        port_ips = self._generate_port_configs_with_global_ips(
            plane_id=plane_id,
            leaf_id=leaf_id,
            topology=topology,
            mapper=mapper
        )
        
        print(f"   Configured Ports: {len(port_ips)}")
        
        # Validate port count (compare logical connections to effective ports)
        expected_connections = topology.total_servers * topology.gpus_per_leaf
        if len(port_ips) != expected_connections:
            print(f"   ⚠️ Warning: Expected {expected_connections} connections, got {len(port_ips)}")
        
        # CRITICAL FIX: Compare against effective_ports, not physical_port_count
        if len(port_ips) > effective_ports:
            raise ValueError(
                f"Topology requires {len(port_ips)} connections but switch only has "
                f"{effective_ports} effective ports ({physical_port_count} physical × {topology.cable_split} split). "
                f"Switch model {model} is insufficient for this topology."
            )
        
        # Step 3: Generate vendor-specific script
        vendor_lower = vendor.lower()
        
        if "nvidia" in vendor_lower or "mellanox" in vendor_lower:
            script_content = self._generate_nvidia_script_gpu_aware(
                switch_id, plane_id, leaf_id, mgmt_ip, port_ips, 
                interface_prefix, os_version, topology
            )
            script_type = "cli"
        elif "arista" in vendor_lower:
            script_content = self._generate_arista_script_gpu_aware(
                switch_id, plane_id, leaf_id, mgmt_ip, port_ips,
                interface_prefix, os_version, topology
            )
            script_type = "cli"
        elif "cisco" in vendor_lower:
            script_content = self._generate_cisco_script_gpu_aware(
                switch_id, plane_id, leaf_id, mgmt_ip, port_ips,
                interface_prefix, os_version, topology
            )
            script_type = "cli"
        else:
            script_content = self._generate_generic_script_gpu_aware(
                switch_id, plane_id, leaf_id, mgmt_ip, port_ips,
                interface_prefix, os_version, topology
            )
            script_type = "cli"
        
        print(f"✅ ZTP script generated ({len(script_content)} bytes)")
        
        return {
            "script_content": script_content,
            "script_type": script_type,
            "port_count": physical_port_count,
            "configured_ports": len(port_ips),
            "vendor": vendor,
            "model": model,
            "switch_id": switch_id,
            "plane_id": plane_id,
            "leaf_id": leaf_id,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
    
    def _generate_port_configs_with_global_ips(
        self,
        plane_id: int,
        leaf_id: int,
        topology: ClusterTopology,
        mapper: GPUToLeafMapper
    ) -> list:
        """Generate port configurations using GLOBAL IP addressing.
        
        This replaces the old P2PIPAllocator with IPSchemaOrchestrator for
        multi-SU aware IP allocation.
        
        Args:
            plane_id: Plane ID (0-indexed)
            leaf_id: Leaf ID (1-indexed)
            topology: Cluster topology with SU awareness
            mapper: GPU-to-Leaf mapper
            
        Returns:
            List of port config dicts with global IPs:
            [
                {
                    'port_number': 1,
                    'switch_ip': '100.126.1.1',  # Global IP
                    'gpu_ip': '100.126.1.0',     # Global IP
                    'subnet': '100.126.1.0/31',  # P2P subnet
                    'description': 'SU1-Rack1-Srv0-GPU0',
                    'rack': 1,
                    'server': 0,
                    'gpu': 0
                },
                ...
            ]
        """
        if not self.ip_orchestrator:
            raise ValueError(
                "IPSchemaOrchestrator required for global IP allocation. "
                "Initialize JITZTPGenerator with ip_orchestrator parameter."
            )
        
        print("\n🌐 Generating port configs with GLOBAL IP schema...")
        print(f"   Leaf {leaf_id}, Plane {plane_id}")
        print(f"   SU {topology.SU_ID}/{topology.SU_COUNT}")
        
        port_configs = []
        port_num = 1
        
        # Iterate through all racks in this SU
        for rack_idx in range(1, topology.R + 1):  # 1-indexed local rack IDs
            # Iterate through all servers in this rack
            for server_idx in range(topology.S):
                # Get the GPU index connected to this leaf
                gpu_idx = mapper.get_gpu_for_leaf(leaf_id, plane_id)
                
                if gpu_idx is None:
                    print(f"   ⚠️ No GPU mapping for Leaf {leaf_id}, Plane {plane_id}")
                    continue
                
                # Generate GLOBAL GPU IP using IPSchemaOrchestrator
                gpu_ip = self.ip_orchestrator.generate_gpu_ip(
                    su_rack_id=rack_idx,  # Local rack ID within SU
                    server_idx=server_idx,
                    gpu_idx=gpu_idx,
                    plane_id=plane_id
                )
                
                # Calculate switch-side IP (GPU IP + 1 for /31 P2P link)
                gpu_ip_parts = gpu_ip.split('.')
                last_octet = int(gpu_ip_parts[3])
                gpu_ip_parts[3] = str(last_octet + 1)
                switch_ip = '.'.join(gpu_ip_parts)
                
                # Build subnet string
                subnet = f"{gpu_ip}/31"
                
                # Build description with GPU_GLOBAL_ID for instant IP-to-location traceability
                global_rack = topology.get_global_rack_id(rack_idx)
                description = f"GPU_GLOBAL_ID_{gpu_ip}_SU{topology.SU_ID}_GlobalRack{global_rack}_Srv{server_idx}_GPU{gpu_idx}_P{plane_id}"
                
                port_configs.append({
                    'port_number': port_num,
                    'switch_ip': switch_ip,
                    'gpu_ip': gpu_ip,
                    'subnet': subnet,
                    'description': description,
                    'rack': rack_idx,
                    'server': server_idx,
                    'gpu': gpu_idx,
                    'global_rack': global_rack
                })
                
                port_num += 1
        
        print(f"   ✅ Generated {len(port_configs)} port configs with global IPs")
        print(f"   IP Range Example: {port_configs[0]['gpu_ip']} → {port_configs[-1]['gpu_ip']}")
        
        return port_configs
    
    # Legacy method for backward compatibility
    def generate_ztp_script(
        self,
        switch_id: str,
        role: str,
        vendor: str,
        model: str,
        mgmt_ip: str,
        fetcher=None
    ) -> Dict:
        """[DEPRECATED] Generate ZTP configuration script (legacy sequential mode).
        
        This method is kept for backward compatibility with management networks.
        For GPU cluster deployments, use generate_full_config() instead.
        
        Args:
            switch_id: Switch identifier
            role: Switch role (e.g., "BACKEND_LEAF")
            vendor: Vendor name
            model: Model number
            mgmt_ip: Management IP
            fetcher: DatasheetFetcher instance
            
        Returns:
            Dict with script_content and metadata
        """
        print("\n⚠️ Using LEGACY sequential port allocation mode")
        print("   For GPU clusters, use generate_full_config() with topology")
        print(f"\n⚙️ Generating ZTP script for {switch_id}")
        print(f"   Vendor: {vendor} {model}")
        print(f"   Role: {role}")
        print(f"   Management IP: {mgmt_ip}")
        
        # Step 1: Get hardware specs (from cache or fetch)
        specs = self.switch_db.get_or_learn_specs(vendor, model, fetcher)
        port_count = specs['data_port_count']
        interface_prefix = specs['interface_prefix']
        os_version = specs['os_version']
        
        print(f"   Port Count: {port_count}")
        print(f"   Interface Template: {interface_prefix}")
        
        # Step 2: Allocate IPs for all ports
        port_ips = self.ip_allocator.allocate_port_range(switch_id, role, port_count)
        
        # Step 3: Generate vendor-specific script
        vendor_lower = vendor.lower()
        
        if "nvidia" in vendor_lower or "mellanox" in vendor_lower:
            script_content = self._generate_nvidia_script(
                switch_id, role, mgmt_ip, port_ips, interface_prefix, os_version
            )
            script_type = "cli"
        elif "arista" in vendor_lower:
            script_content = self._generate_arista_script(
                switch_id, role, mgmt_ip, port_ips, interface_prefix, os_version
            )
            script_type = "cli"
        elif "cisco" in vendor_lower:
            script_content = self._generate_cisco_script(
                switch_id, role, mgmt_ip, port_ips, interface_prefix, os_version
            )
            script_type = "cli"
        else:
            # Generic script for unknown vendors
            script_content = self._generate_generic_script(
                switch_id, role, mgmt_ip, port_ips, interface_prefix, os_version
            )
            script_type = "cli"
        
        print(f"✅ ZTP script generated ({len(script_content)} bytes)")
        
        return {
            "script_content": script_content,
            "script_type": script_type,
            "port_count": port_count,
            "vendor": vendor,
            "model": model,
            "switch_id": switch_id,
            "role": role,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
    
    def generate_discovery_script(self, mac_address: str, callback_url: str) -> str:
        """Generate minimal Stage 1 discovery script for serial number extraction.
        
        This script runs on unconfigured switches to report their identity.
        Solves the "Pre-ZTP Connectivity Paradox" where fresh switches have
        no SSH/SNMP enabled for remote queries.
        
        The script:
        1. Extracts serial number using dmidecode or vendor-specific commands
        2. Extracts vendor/model information if available
        3. POSTs to callback URL (/ztp/discovery)
        4. Downloads full config after verification
        
        Args:
            mac_address: MAC address of switch (for identification)
            callback_url: Full URL to POST discovery data (e.g., "https://yourapp.com/api/ztp/discovery")
            
        Returns:
            Bash script content as string
            
        Example Output:
            #!/bin/bash
            SERIAL=$(dmidecode -s system-serial-number)
            curl -X POST https://yourapp.com/api/ztp/discovery \\
              -H "Content-Type: application/json" \\
              -d '{"mac":"00:1B:...","serial":"'$SERIAL'"}'
        """
        # Normalize MAC for consistency
        mac_normalized = mac_address.upper().replace("-", ":").replace(".", ":")
        
        # Extract base URL for config download
        config_url = callback_url.replace("/discovery", f"/config/{mac_address}")
        
        script = f'''#!/bin/bash
# ZTP Stage 1: Discovery Script
# Auto-generated for switch MAC: {mac_normalized}
#
# Purpose: Extract hardware identity and report to provisioning API
# This avoids the need for SSH/SNMP access to unconfigured switches

echo "====================================="
echo "ZTP Discovery Stage 1 Starting..."
echo "MAC Address: {mac_normalized}"
echo "====================================="

# Extract serial number (try multiple methods)
SERIAL="UNKNOWN"

# Method 1: dmidecode (most common)
if command -v dmidecode &> /dev/null; then
    SERIAL=$(dmidecode -s system-serial-number 2>/dev/null | tr -d '\\n' | tr -d ' ')
    echo "Serial (dmidecode): $SERIAL"
fi

# Method 2: System files (fallback)
if [ "$SERIAL" = "UNKNOWN" ] && [ -f /sys/class/dmi/id/product_serial ]; then
    SERIAL=$(cat /sys/class/dmi/id/product_serial | tr -d '\\n' | tr -d ' ')
    echo "Serial (sysfs): $SERIAL"
fi

# Method 3: Vendor-specific commands
if [ "$SERIAL" = "UNKNOWN" ]; then
    # NVIDIA/Mellanox: Try getting from firmware
    if command -v flint &> /dev/null; then
        SERIAL=$(flint -d /dev/mst/mt4123_pciconf0 query | grep "PSID" | awk '{{print $2}}')
        echo "Serial (flint): $SERIAL"
    fi
fi

# Extract vendor/model information
VENDOR="UNKNOWN"
MODEL="UNKNOWN"

if command -v dmidecode &> /dev/null; then
    VENDOR=$(dmidecode -s system-manufacturer 2>/dev/null | tr -d '\\n')
    MODEL=$(dmidecode -s system-product-name 2>/dev/null | tr -d '\\n')
    echo "Vendor: $VENDOR"
    echo "Model: $MODEL"
fi

# Report to provisioning API
echo "====================================="
echo "Reporting identity to API..."
echo "Callback URL: {callback_url}"
echo "====================================="

curl -X POST "{callback_url}" \\
  -H "Content-Type: application/json" \\
  -d '{{"mac":"{mac_normalized}","serial":"'$SERIAL'","vendor":"'$VENDOR'","model":"'$MODEL'"}}' \\
  --max-time 30 \\
  --retry 3 \\
  --retry-delay 5

if [ $? -eq 0 ]; then
    echo "✅ Identity reported successfully"
    
    # Wait for API to verify and generate config
    echo "⏳ Waiting for configuration generation..."
    sleep 10
    
    # Download full configuration script
    echo "📥 Downloading full ZTP configuration..."
    curl -o /tmp/full_ztp_config.sh "{config_url}" \\
      --max-time 60 \\
      --retry 5 \\
      --retry-delay 5
    
    if [ $? -eq 0 ]; then
        echo "✅ Configuration downloaded successfully"
        
        # Make executable and run
        chmod +x /tmp/full_ztp_config.sh
        echo "🚀 Executing full configuration..."
        bash /tmp/full_ztp_config.sh
        
        echo "====================================="
        echo "✅ ZTP Provisioning Complete"
        echo "====================================="
    else
        echo "❌ Failed to download configuration"
        echo "Check API endpoint: {config_url}"
        exit 1
    fi
else
    echo "❌ Failed to report identity to API"
    echo "Check network connectivity and API endpoint"
    exit 1
fi
'''
        
        return script
    
    def _generate_nvidia_script(
        self,
        switch_id: str,
        role: str,
        mgmt_ip: str,
        port_ips: list,
        interface_prefix: str,
        os_version: str
    ) -> str:
        """Generate ZTP script for NVIDIA/Mellanox switches (Onyx OS).
        
        Onyx uses a Linux-based CLI with specific command syntax.
        
        Args:
            switch_id: Hostname to set
            role: Switch role (for comments)
            mgmt_ip: Management IP
            port_ips: List of port IP allocations
            interface_prefix: Interface naming template
            os_version: Target OS version
            
        Returns:
            CLI command script as string
        """
        lines = [
            "#!/bin/bash",
            f"# Auto-generated ZTP configuration for {switch_id}",
            f"# Role: {role}",
            f"# Generated: {datetime.utcnow().isoformat()}Z",
            f"# OS: {os_version}",
            "",
            "# Enter configuration mode",
            "cli",
            "configure terminal",
            "",
            "# Set hostname",
            f"hostname {switch_id}",
            "",
            "# Management interface",
            "interface mgmt0",
            f"  ip address {mgmt_ip}/24",
            "  no shutdown",
            "",
            "# Configure data ports",
        ]
        
        # Add port configurations
        for port in port_ips:
            port_num = port['port_number']
            ip_addr = port['ip_address']
            interface_name = interface_prefix.format(id=port_num)
            
            lines.extend([
                f"interface {interface_name}",
                f"  description {role} Port {port_num}",
                f"  ip address {ip_addr}",
                "  no shutdown",
                ""
            ])
        
        lines.extend([
            "# Save configuration",
            "exit",
            "write memory",
            "",
            "# ZTP complete",
            "echo \"ZTP configuration applied successfully\"",
        ])
        
        return "\n".join(lines)
    
    def _generate_arista_script(
        self,
        switch_id: str,
        role: str,
        mgmt_ip: str,
        port_ips: list,
        interface_prefix: str,
        os_version: str
    ) -> str:
        """Generate ZTP script for Arista switches (EOS).
        
        EOS uses a similar CLI to Cisco IOS but with some differences.
        
        Args:
            switch_id: Hostname to set
            role: Switch role
            mgmt_ip: Management IP
            port_ips: Port IP allocations
            interface_prefix: Interface naming
            os_version: Target OS version
            
        Returns:
            EOS CLI command script
        """
        lines = [
            "#!/usr/bin/env python3",
            f"# Auto-generated ZTP configuration for {switch_id}",
            f"# Role: {role}",
            f"# Generated: {datetime.utcnow().isoformat()}Z",
            f"# OS: {os_version}",
            "",
            "from jsonrpclib import Server",
            "switch = Server('http://localhost/command-api')",
            "",
            "commands = [",
            "    'enable',",
            "    'configure terminal',",
            f"    'hostname {switch_id}',",
            "    'interface Management1',",
            f"    'ip address {mgmt_ip}/24',",
            "    'no shutdown',",
        ]
        
        # Add port configurations
        for port in port_ips:
            port_num = port['port_number']
            ip_addr = port['ip_address']
            interface_name = interface_prefix.format(id=port_num)
            
            lines.append(f"    'interface {interface_name}',")
            lines.append(f"    'description {role} Port {port_num}',")
            lines.append(f"    'ip address {ip_addr}',")
            lines.append("    'no shutdown',")
        
        lines.extend([
            "    'exit',",
            "    'write memory'",
            "]",
            "",
            "switch.runCmds(1, commands)",
            "print('ZTP configuration applied successfully')",
        ])
        
        return "\n".join(lines)
    
    def _generate_cisco_script(
        self,
        switch_id: str,
        role: str,
        mgmt_ip: str,
        port_ips: list,
        interface_prefix: str,
        os_version: str
    ) -> str:
        """Generate ZTP script for Cisco switches (NX-OS).
        
        Args:
            switch_id: Hostname to set
            role: Switch role
            mgmt_ip: Management IP
            port_ips: Port IP allocations
            interface_prefix: Interface naming
            os_version: Target OS version
            
        Returns:
            NX-OS CLI command script
        """
        lines = [
            "#!/bin/bash",
            f"# Auto-generated ZTP configuration for {switch_id}",
            f"# Role: {role}",
            f"# Generated: {datetime.utcnow().isoformat()}Z",
            f"# OS: {os_version}",
            "",
            "configure terminal",
            f"hostname {switch_id}",
            "",
            "interface mgmt0",
            f"  ip address {mgmt_ip}/24",
            "  no shutdown",
            "",
        ]
        
        # Add port configurations
        for port in port_ips:
            port_num = port['port_number']
            ip_addr = port['ip_address']
            interface_name = interface_prefix.format(id=port_num)
            
            lines.extend([
                f"interface {interface_name}",
                f"  description {role} Port {port_num}",
                f"  ip address {ip_addr}",
                "  no shutdown",
                ""
            ])
        
        lines.extend([
            "exit",
            "copy running-config startup-config",
            "echo ZTP configuration applied successfully",
        ])
        
        return "\n".join(lines)
    
    def _generate_generic_script(
        self,
        switch_id: str,
        role: str,
        mgmt_ip: str,
        port_ips: list,
        interface_prefix: str,
        os_version: str
    ) -> str:
        """Generate generic ZTP script for unknown vendors.
        
        Falls back to a simple CLI-style script that works with
        most switch operating systems.
        
        Args:
            switch_id: Hostname to set
            role: Switch role
            mgmt_ip: Management IP
            port_ips: Port IP allocations
            interface_prefix: Interface naming
            os_version: Target OS version
            
        Returns:
            Generic CLI command script
        """
        lines = [
            "#!/bin/bash",
            f"# Auto-generated ZTP configuration for {switch_id}",
            f"# Role: {role}",
            f"# Generated: {datetime.utcnow().isoformat()}Z",
            f"# OS: {os_version}",
            "# WARNING: Generic script - verify commands for your vendor",
            "",
            "configure terminal",
            f"hostname {switch_id}",
            "",
            "# Management interface",
            "interface mgmt",
            f"  ip address {mgmt_ip}/24",
            "  no shutdown",
            "",
            "# Data port configuration",
        ]
        
        # Add port configurations
        for port in port_ips:
            port_num = port['port_number']
            ip_addr = port['ip_address']
            interface_name = interface_prefix.format(id=port_num)
            
            lines.extend([
                f"interface {interface_name}",
                f"  description {role} Port {port_num}",
                f"  ip address {ip_addr}",
                "  no shutdown",
                ""
            ])
        
        lines.extend([
            "exit",
            "write memory",
            "echo Configuration complete",
        ])
        
        return "\n".join(lines)
    
    def _generate_nvidia_script_gpu_aware(
        self,
        switch_id: str,
        plane_id: int,
        leaf_id: int,
        mgmt_ip: str,
        port_ips: list,
        interface_prefix: str,
        os_version: str,
        topology: ClusterTopology
    ) -> str:
        """Generate GPU-aware NVIDIA/Mellanox ZTP script.
        
        Each port is configured with:
        - Expected GPU connection info in description
        - Server-side IP (GPU interface IP)
        - Switch-side IP (switch port IP)
        - /31 point-to-point subnet
        
        Args:
            switch_id: Hostname to set
            plane_id: Plane ID
            leaf_id: Leaf ID
            mgmt_ip: Management IP
            port_ips: GPU-aware port IP allocations from P2PIPAllocator
            interface_prefix: Interface naming template
            os_version: Target OS version
            topology: ClusterTopology instance
            
        Returns:
            CLI command script as string
        """
        lines = [
            "#!/bin/bash",
            "# Auto-generated GPU-Aware ZTP Configuration",
            f"# Switch: {switch_id}",
            f"# Plane: {plane_id}, Leaf: {leaf_id}",
            f"# Topology: {topology.G} GPUs/server, {topology.L} Leafs/plane",
            f"# Cable Configuration: {topology.cable_split}:1 breakout",
            f"# Generated: {datetime.utcnow().isoformat()}Z",
            f"# OS: {os_version}",
            "",
            "# Enter configuration mode",
            "cli",
            "configure terminal",
            "",
            "# Set hostname",
            f"hostname {switch_id}",
            "",
            "# Management interface",
            "interface mgmt0",
            f"  ip address {mgmt_ip}/24",
            "  no shutdown",
            "",
        ]
        
        # Add port breakout configuration if needed
        if topology.cable_split > 1:
            lines.extend([
                f"# Configure port breakout ({topology.cable_split}:1 split)",
                f"# Splits each physical OSFP port into {topology.cable_split} logical ports",
                ""
            ])
            
            # Determine which physical ports need splitting
            # Get unique physical port numbers from port_ips
            physical_ports = set()
            for port_config in port_ips:
                port_num = port_config['port_number']
                # Calculate physical port: logical port divided by split factor
                physical_port = ((port_num - 1) // topology.cable_split) + 1
                physical_ports.add(physical_port)
            
            # Generate split commands for each physical port
            for phys_port in sorted(physical_ports):
                interface_name = interface_prefix.format(id=phys_port)
                lines.append(f"interface {interface_name} module-type qsfp-split-{topology.cable_split}")
            
            lines.append("")
        
        lines.extend([
            "# Configure data ports (GPU-aware topology)",
            "# Each port expects a specific GPU based on cluster topology",
            "",
        ])
        
        # Add GPU-aware port configurations
        for port_config in port_ips:
            port_num = port_config['port_number']
            switch_ip = port_config['switch_ip']
            subnet = port_config['subnet']
            description = port_config['description']
            rack = port_config['rack']
            server = port_config['server']
            gpu = port_config['gpu']
            
            interface_name = interface_prefix.format(id=port_num)
            
            lines.extend([
                f"interface {interface_name}",
                f"  description {description}",
                f"  # Expects: Rack {rack}, Server {server}, GPU {gpu}",
                f"  ip address {subnet}",
                "  no shutdown",
                ""
            ])
        
        lines.extend([
            "# Save configuration",
            "exit",
            "write memory",
            "",
            "# ZTP complete",
            f"echo 'GPU-aware ZTP configuration applied: {len(port_ips)} ports configured'",
        ])
        
        return "\n".join(lines)
    
    def _generate_arista_script_gpu_aware(
        self,
        switch_id: str,
        plane_id: int,
        leaf_id: int,
        mgmt_ip: str,
        port_ips: list,
        interface_prefix: str,
        os_version: str,
        topology: ClusterTopology
    ) -> str:
        """Generate GPU-aware Arista EOS ZTP script."""
        lines = [
            "#!/usr/bin/env python3",
            "# Auto-generated GPU-Aware ZTP Configuration",
            f"# Switch: {switch_id}",
            f"# Plane: {plane_id}, Leaf: {leaf_id}",
            f"# Topology: {topology.G} GPUs/server, {topology.L} Leafs/plane",
            f"# Cable Configuration: {topology.cable_split}:1 breakout",
            f"# Generated: {datetime.utcnow().isoformat()}Z",
            f"# OS: {os_version}",
            "",
            "from jsonrpclib import Server",
            "switch = Server('http://localhost/command-api')",
            "",
            "commands = [",
            "    'enable',",
            "    'configure terminal',",
            f"    'hostname {switch_id}',",
            "    'interface Management1',",
            f"    'ip address {mgmt_ip}/24',",
            "    'no shutdown',",
        ]
        
        # Add port breakout configuration if needed
        if topology.cable_split > 1:
            lines.append(f"    '! Configure port breakout ({topology.cable_split}:1 split)',")
            
            # Determine which physical ports need splitting
            physical_ports = set()
            for port_config in port_ips:
                port_num = port_config['port_number']
                physical_port = ((port_num - 1) // topology.cable_split) + 1
                physical_ports.add(physical_port)
            
            # Arista uses 'interface breakout' command
            for phys_port in sorted(physical_ports):
                interface_name = interface_prefix.format(id=phys_port)
                lines.append(f"    'interface {interface_name}',")
                lines.append(f"    'speed forced {400 // topology.cable_split}gfull',")
                lines.append(f"    'breakout {topology.cable_split}x{100 // (topology.cable_split // 4 or 1)}g',")
            
            lines.append("    '!',")
        
        # Add GPU-aware port configurations
        for port_config in port_ips:
            port_num = port_config['port_number']
            subnet = port_config['subnet']
            description = port_config['description']
            interface_name = interface_prefix.format(id=port_num)
            
            lines.append(f"    'interface {interface_name}',")
            lines.append(f"    'description {description}',")
            lines.append(f"    'ip address {subnet}',")
            lines.append("    'no shutdown',")
        
        lines.extend([
            "    'exit',",
            "    'write memory'",
            "]",
            "",
            "switch.runCmds(1, commands)",
            f"print('GPU-aware ZTP configuration applied: {len(port_ips)} ports configured')",
        ])
        
        return "\n".join(lines)
    
    def _generate_cisco_script_gpu_aware(
        self,
        switch_id: str,
        plane_id: int,
        leaf_id: int,
        mgmt_ip: str,
        port_ips: list,
        interface_prefix: str,
        os_version: str,
        topology: ClusterTopology
    ) -> str:
        """Generate GPU-aware Cisco NX-OS ZTP script."""
        lines = [
            "#!/bin/bash",
            "# Auto-generated GPU-Aware ZTP Configuration",
            f"# Switch: {switch_id}",
            f"# Plane: {plane_id}, Leaf: {leaf_id}",
            f"# Topology: {topology.G} GPUs/server, {topology.L} Leafs/plane",
            f"# Generated: {datetime.utcnow().isoformat()}Z",
            f"# OS: {os_version}",
            "",
            "configure terminal",
            f"hostname {switch_id}",
            "",
            "interface mgmt0",
            f"  ip address {mgmt_ip}/24",
            "  no shutdown",
            "",
        ]
        
        # Add GPU-aware port configurations
        for port_config in port_ips:
            port_num = port_config['port_number']
            subnet = port_config['subnet']
            description = port_config['description']
            interface_name = interface_prefix.format(id=port_num)
            
            lines.extend([
                f"interface {interface_name}",
                f"  description {description}",
                f"  ip address {subnet}",
                "  no shutdown",
                ""
            ])
        
        lines.extend([
            "exit",
            "copy running-config startup-config",
            f"echo GPU-aware ZTP configuration applied: {len(port_ips)} ports configured",
        ])
        
        return "\n".join(lines)
    
    def _generate_generic_script_gpu_aware(
        self,
        switch_id: str,
        plane_id: int,
        leaf_id: int,
        mgmt_ip: str,
        port_ips: list,
        interface_prefix: str,
        os_version: str,
        topology: ClusterTopology
    ) -> str:
        """Generate GPU-aware generic ZTP script."""
        lines = [
            "#!/bin/bash",
            "# Auto-generated GPU-Aware ZTP Configuration",
            f"# Switch: {switch_id}",
            f"# Plane: {plane_id}, Leaf: {leaf_id}",
            f"# Topology: {topology.G} GPUs/server, {topology.L} Leafs/plane",
            f"# Generated: {datetime.utcnow().isoformat()}Z",
            f"# OS: {os_version}",
            "# WARNING: Generic script - verify commands for your vendor",
            "",
            "configure terminal",
            f"hostname {switch_id}",
            "",
            "interface mgmt",
            f"  ip address {mgmt_ip}/24",
            "  no shutdown",
            "",
        ]
        
        # Add GPU-aware port configurations
        for port_config in port_ips:
            port_num = port_config['port_number']
            subnet = port_config['subnet']
            description = port_config['description']
            interface_name = interface_prefix.format(id=port_num)
            
            lines.extend([
                f"interface {interface_name}",
                f"  description {description}",
                f"  ip address {subnet}",
                "  no shutdown",
                ""
            ])
        
        lines.extend([
            "exit",
            "write memory",
            f"echo GPU-aware ZTP configuration applied: {len(port_ips)} ports configured",
        ])
        
        return "\n".join(lines)
    
    def save_ztp_script(self, script_data: Dict) -> str:
        """Save ZTP script to storage for switch download.
        
        The script is saved with a predictable filename based on
        switch ID, allowing the DHCP server to provide the correct
        URL via Option 67.
        
        Args:
            script_data: Output from generate_ztp_script()
            
        Returns:
            Storage key where script was saved
            
        Example:
            >>> key = generator.save_ztp_script(script_data)
            >>> print(key)
            "ztp_scripts/SW-RACK04-LEAF1.sh"
        """
        import databutton as db
        
        switch_id = script_data['switch_id']
        script_content = script_data['script_content']
        
        # Sanitize switch_id for use as filename
        safe_id = switch_id.replace("/", "_").replace(" ", "_")
        
        # Determine file extension based on script type
        ext_map = {
            "bash": "sh",
            "python": "py",
            "cli": "cfg"
        }
        ext = ext_map.get(script_data['script_type'], 'txt')
        
        # Save to storage
        storage_key = f"ztp_scripts/{safe_id}.{ext}"
        db.storage.text.put(storage_key, script_content)
        
        print(f"💾 Saved ZTP script to storage: {storage_key}")
        
        return storage_key
    
    def get_ztp_url(self, storage_key: str, base_url: str) -> str:
        """Construct public URL for ZTP script download.
        
        This URL is provided to the switch via DHCP Option 67.
        
        Args:
            storage_key: Storage key from save_ztp_script()
            base_url: Base URL of the application
            
        Returns:
            Full URL for script download
            
        Example:
            >>> url = generator.get_ztp_url(
            ...     "ztp_scripts/SW-RACK04-LEAF1.sh",
            ...     "https://yourapp.riff.works"
            ... )
            >>> print(url)
            "https://yourapp.riff.works/ztp/SW-RACK04-LEAF1.sh"
        """
        filename = storage_key.split('/')[-1]
        return f"{base_url}/ztp/{filename}"
