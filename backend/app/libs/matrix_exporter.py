"""Cabling matrix CSV exporter for GPU cluster deployment."""

import csv
import io
from typing import List, Dict, Any
from app.libs.firebase_config import get_firestore_client
from app.libs.firestore_scoping import get_scoped_collection

def generate_cabling_matrix_csv(project_id: str, customer_id: str = "default") -> str:
    """
    Generate a deployment-ready cabling matrix CSV organized by server type.
    
    Format:
    GPU-Server, Location, ServerPort, Switch1Port, Switch1, Switch2Port, Switch2, 
    Switch3Port, Switch3, Switch4Port, Switch4, FabricType, EdgeSwitch1, EdgeSwitch1Port
    
    Repeated for Storage servers and CPU servers.
    """
    firestore_client = get_firestore_client()
    
    # Fetch project details
    project_doc = get_scoped_collection(firestore_client, customer_id, "cluster_bringup_projects").document(project_id).get()
    if not project_doc.exists:
        raise ValueError(f"Project {project_id} not found")
    
    project_data = project_doc.to_dict()
    
    # Fetch devices
    devices_query = get_scoped_collection(firestore_client, customer_id, "extracted_devices").where("projectId", "==", project_id).stream()
    devices = {doc.to_dict()["deviceName"]: doc.to_dict() for doc in devices_query}
    
    # Fetch connections
    connections_query = get_scoped_collection(firestore_client, customer_id, "extracted_connections").where("projectId", "==", project_id).stream()
    connections = [doc.to_dict() for doc in connections_query]
    
    # Build connectivity map
    server_connectivity = build_server_connectivity_map(devices, connections)
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Server",
        "Location",
        "ServerPort",
        "Switch1Port",
        "Switch1",
        "Switch2Port",
        "Switch2",
        "Switch3Port",
        "Switch3",
        "Switch4Port",
        "Switch4",
        "FabricType",
        "EdgeSwitch",
        "EdgeSwitchPort"
    ])
    
    # GPU Servers
    writer.writerow([])  # Blank line
    writer.writerow(["=== GPU SERVERS ==="])
    gpu_servers = {name: data for name, data in server_connectivity.items() 
                   if devices.get(name, {}).get('deviceType') == 'compute'}
    for server_name in sorted(gpu_servers.keys()):
        write_server_rows(writer, server_name, gpu_servers[server_name], devices)
    
    # Storage Servers
    writer.writerow([])  # Blank line
    writer.writerow(["=== STORAGE SERVERS ==="])
    storage_servers = {name: data for name, data in server_connectivity.items() 
                       if devices.get(name, {}).get('deviceType') == 'storage'}
    for server_name in sorted(storage_servers.keys()):
        write_server_rows(writer, server_name, storage_servers[server_name], devices)
    
    # CPU Servers (if any other compute types exist)
    writer.writerow([])  # Blank line
    writer.writerow(["=== CPU SERVERS ==="])
    cpu_servers = {name: data for name, data in server_connectivity.items() 
                   if devices.get(name, {}).get('deviceType') == 'other'}
    for server_name in sorted(cpu_servers.keys()):
        write_server_rows(writer, server_name, cpu_servers[server_name], devices)
    
    # Add summary section
    writer.writerow([])
    writer.writerow([])
    writer.writerow(["=== SUMMARY ==="])
    writer.writerow(["Total GPU Servers", len(gpu_servers)])
    writer.writerow(["Total Storage Servers", len(storage_servers)])
    writer.writerow(["Total CPU Servers", len(cpu_servers)])
    writer.writerow(["Total Connections", len(connections)])
    
    # Project metadata
    writer.writerow([])
    writer.writerow(["=== PROJECT METADATA ==="])
    writer.writerow(["Project ID", project_id])
    writer.writerow(["Project Name", project_data.get("projectName", "Unknown")])
    writer.writerow(["Generated", project_data.get("completedAt", "Unknown")])
    
    csv_content = output.getvalue()
    output.close()
    
    return csv_content


def build_server_connectivity_map(devices: Dict[str, Any], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a map of server connectivity through the network fabric.
    
    Returns: {server_name: {ports: [{path: [...switches...], fabric_type: str, edge: {...}}]}}
    """
    server_map = {}
    
    # Identify servers (compute, storage, other)
    servers = {name: data for name, data in devices.items() 
               if data.get('deviceType') in ['compute', 'storage', 'other']}
    
    for server_name in servers:
        server_map[server_name] = {'ports': []}
        
        # Find all connections from this server
        server_connections = [c for c in connections 
                              if c.get('sourceDevice') == server_name or c.get('destinationDevice') == server_name]
        
        for conn in server_connections:
            # Determine direction (server as source or destination)
            if conn.get('sourceDevice') == server_name:
                server_port = conn.get('sourcePort')
                next_hop = conn.get('destinationDevice')
                next_hop_port = conn.get('destinationPort')
            else:
                server_port = conn.get('destinationPort')
                next_hop = conn.get('sourceDevice')
                next_hop_port = conn.get('sourcePort')
            
            # Trace the path through switches
            path = trace_switch_path(next_hop, next_hop_port, connections, devices)
            
            server_map[server_name]['ports'].append({
                'server_port': server_port,
                'fabric_type': conn.get('connectionType', 'Unknown'),
                'bandwidth': conn.get('bandwidth', 'Unknown'),
                'path': path
            })
    
    return server_map


def trace_switch_path(start_device: str, start_port: str, connections: List[Dict[str, Any]], devices: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Trace the path through switches from a starting point.
    
    Returns: [{switch: str, in_port: str, out_port: str, next_switch: str}, ...]
    """
    path = []
    current_device = start_device
    current_port = start_port
    visited = set()
    max_hops = 10  # Prevent infinite loops
    
    for _ in range(max_hops):
        if current_device in visited:
            break
        
        device_type = devices.get(current_device, {}).get('deviceType', '')
        
        # Stop if we've reached an edge/uplink device or non-switch
        if 'switch' not in device_type:
            # This might be an edge router or uplink
            if device_type in ['other', 'router', 'firewall']:
                path.append({
                    'switch': current_device,
                    'in_port': current_port,
                    'out_port': None,
                    'next_switch': None,
                    'is_edge': True
                })
            break
        
        visited.add(current_device)
        
        # Find next hop from this switch
        next_hops = [c for c in connections 
                     if (c.get('sourceDevice') == current_device and c.get('sourcePort') != current_port) or
                        (c.get('destinationDevice') == current_device and c.get('destinationPort') != current_port)]
        
        if not next_hops:
            # Dead end - this is likely the edge switch
            path.append({
                'switch': current_device,
                'in_port': current_port,
                'out_port': None,
                'next_switch': None,
                'is_edge': True
            })
            break
        
        # Take the first uplink (prefer spine switches)
        next_hop = next_hops[0]
        
        if next_hop.get('sourceDevice') == current_device:
            out_port = next_hop.get('sourcePort')
            next_device = next_hop.get('destinationDevice')
            next_in_port = next_hop.get('destinationPort')
        else:
            out_port = next_hop.get('destinationPort')
            next_device = next_hop.get('sourceDevice')
            next_in_port = next_hop.get('sourcePort')
        
        path.append({
            'switch': current_device,
            'in_port': current_port,
            'out_port': out_port,
            'next_switch': next_device,
            'is_edge': False
        })
        
        current_device = next_device
        current_port = next_in_port
    
    return path


def write_server_rows(writer, server_name: str, server_data: Dict[str, Any], devices: Dict[str, Any]):
    """
    Write rows for a server's connectivity including hardware verification details.
    """
    device = devices.get(server_name, {})
    
    # Location hierarchy
    site = device.get('site', '')
    room = device.get('room', '')
    row = device.get('row', '')
    rack = device.get('rack', '')
    u_position = device.get('uPosition', '')
    
    # Hardware details (from asset inventory merge)
    serial_number = device.get('serialNumber', '')
    asset_tag = device.get('assetTag', '')
    manufacturer = device.get('manufacturer', '')
    model = device.get('model', '')
    
    # Verification status
    verification_status = device.get('verificationStatus', 'Pending')
    status_display = {
        'verified': '✅ Verified',
        'pending': '⏳ Pending',
        'mismatch': '⚠️ Mismatch'
    }.get(verification_status, '⏳ Pending')
    
    for port_data in server_data.get('ports', []):
        path = port_data.get('path', [])
        
        # Extract up to 4 switches from the path
        switch1 = path[0].get('switch', '') if len(path) > 0 else ''
        switch1_port = path[0].get('in_port', '') if len(path) > 0 else ''
        
        switch2 = path[1].get('switch', '') if len(path) > 1 else ''
        switch2_port = path[1].get('in_port', '') if len(path) > 1 else ''
        
        switch3 = path[2].get('switch', '') if len(path) > 2 else ''
        switch3_port = path[2].get('in_port', '') if len(path) > 2 else ''
        
        switch4 = path[3].get('switch', '') if len(path) > 3 else ''
        switch4_port = path[3].get('in_port', '') if len(path) > 3 else ''
        
        # Find edge switch (last switch in path)
        edge_switch = path[-1].get('switch', '') if path else ''
        edge_switch_port = path[-1].get('in_port', '') if path else ''
        
        writer.writerow([
            server_name,
            site,
            room,
            row,
            rack,
            u_position,
            serial_number,
            asset_tag,
            manufacturer,
            model,
            status_display,
            port_data.get('server_port', ''),
            switch1_port,
            switch1,
            switch2_port,
            switch2,
            switch3_port,
            switch3,
            switch4_port,
            switch4,
            port_data.get('fabric_type', ''),
            edge_switch,
            edge_switch_port
        ])


def generate_port_mapping_csv(project_id: str) -> str:
    """
    Generate a port mapping reference CSV (device-centric view).
    
    Format:
    Device Name, Port Label, Connected To, Connection Type, Bandwidth
    """
    firestore_client = get_firestore_client()
    
    # Fetch devices
    devices_query = firestore_client.collection("extracted_devices").where("projectId", "==", project_id).stream()
    devices = {doc.to_dict()["deviceName"]: doc.to_dict() for doc in devices_query}
    
    # Fetch connections
    connections_query = firestore_client.collection("extracted_connections").where("projectId", "==", project_id).stream()
    connections = [doc.to_dict() for doc in connections_query]
    
    # Build port mapping
    port_map = {}
    
    for conn in connections:
        source = conn.get("sourceDevice")
        source_port = conn.get("sourcePort")
        dest = conn.get("destinationDevice")
        dest_port = conn.get("destinationPort")
        conn_type = conn.get("connectionType")
        bandwidth = conn.get("bandwidth")
        
        # Add source-side mapping
        if source not in port_map:
            port_map[source] = []
        port_map[source].append({
            "port": source_port,
            "connectedTo": f"{dest}:{dest_port}",
            "connectionType": conn_type,
            "bandwidth": bandwidth
        })
        
        # Add destination-side mapping
        if dest not in port_map:
            port_map[dest] = []
        port_map[dest].append({
            "port": dest_port,
            "connectedTo": f"{source}:{source_port}",
            "connectionType": conn_type,
            "bandwidth": bandwidth
        })
    
    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(["Device Name", "Port Label", "Connected To", "Connection Type", "Bandwidth"])
    
    # Data rows (sorted by device name)
    for device_name in sorted(port_map.keys()):
        ports = port_map[device_name]
        # Sort ports by port label
        ports.sort(key=lambda p: p["port"])
        
        for port in ports:
            writer.writerow([
                device_name,
                port["port"],
                port["connectedTo"],
                port["connectionType"],
                port["bandwidth"]
            ])
    
    csv_content = output.getvalue()
    output.close()
    
    return csv_content
