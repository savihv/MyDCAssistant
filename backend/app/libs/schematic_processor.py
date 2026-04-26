"""Schematic processor using Gemini Vision API to extract devices and connections from data center diagrams."""

import uuid
import json
from typing import Dict, List, Any
from datetime import datetime
import databutton as db  # type: ignore
from google.cloud import firestore  # type: ignore
from app.libs.gemini_client import get_gemini_client
from app.libs.firebase_config import get_firestore_client
from app.libs.firestore_scoping import get_scoped_collection

# Configure Gemini
genai = get_gemini_client()


def trigger_schematic_processing(project_id: str, customer_id: str = "default"):
    """
    Main entry point for schematic processing.
    Retrieves project configuration and initiates AI extraction.
    
    Args:
        project_id: The project identifier
        customer_id: The customer identifier for data scoping (defaults to "default")
    """
    firestore_client = get_firestore_client()
    
    try:
        # Update status to processing
        project_ref = get_scoped_collection(firestore_client, customer_id, "cluster_bringup_projects").document(project_id)
        project_ref.update({
            "status": "processing",
            "progressPercentage": 0,
            "currentStage": "Initializing"
        })
        
        # Get project configuration
        project_doc = project_ref.get()
        if not project_doc.exists:
            raise ValueError(f"Project {project_id} not found")
        
        project_data = project_doc.to_dict()
        
        # Load schematic from storage
        from app.libs.firebase_config import get_storage_bucket
        schematic_url = project_data.get("schematicUrl")
        bucket = get_storage_bucket()
        blob = bucket.blob(schematic_url)
        schematic_bytes = blob.download_as_bytes()
        
        # Update progress
        project_ref.update({
            "progressPercentage": 10,
            "currentStage": "Loading schematic"
        })
        
        # Extract devices
        devices = extract_devices(
            schematic_bytes,
            project_data.get("colorLegend", {}),
            project_data.get("deviceConventions", {}),
            project_id,
            project_ref,
            customer_id
        )
        
        # Update progress
        project_ref.update({
            "progressPercentage": 50,
            "currentStage": "Extracting connections"
        })
        
        # Extract connections
        connections = extract_connections(
            schematic_bytes,
            project_data.get("colorLegend", {}),
            devices,
            project_data.get("processingConfig", {}),
            project_id,
            project_ref,
            customer_id
        )
        
        # Update progress
        project_ref.update({
            "progressPercentage": 80,
            "currentStage": "Validating topology"
        })
        
        # Validate topology
        validation_report = validate_topology(
            devices,
            connections,
            project_data.get("processingConfig", {}),
            project_id
        )
        
        # Mark as complete
        project_ref.update({
            "status": "completed",
            "progressPercentage": 100,
            "currentStage": "Complete",
            "completedAt": firestore.SERVER_TIMESTAMP
        })
        
        print(f"Processing completed for project {project_id}")
        print(f"Extracted {len(devices)} devices and {len(connections)} connections")
        
    except Exception as e:
        print(f"Processing failed for project {project_id}: {str(e)}")
        project_ref.update({
            "status": "failed",
            "errorMessage": str(e)
        })
        raise


def extract_devices(
    schematic_bytes: bytes,
    color_legend: Dict[str, Any],
    device_conventions: Dict[str, str],
    project_id: str,
    project_ref: Any,
    customer_id: str = "default"
) -> List[Dict[str, Any]]:
    """
    Use Gemini Vision API to extract devices from the schematic.
    """
    
    # Build prompt for device extraction
    device_prompt = f"""
You are analyzing a data center schematic diagram for a GPU cluster deployment. Extract ALL devices visible in the diagram with enhanced network tier classification.

Device Naming Conventions:
- Compute nodes start with: "{device_conventions.get('computePrefix', 'Compute')}"
- Storage arrays start with: "{device_conventions.get('storagePrefix', 'Storage')}"
- Leaf switches start with: "{device_conventions.get('switchLeafPrefix', 'Switch-Leaf')}"
- Spine switches start with: "{device_conventions.get('switchSpinePrefix', 'Switch-Spine')}"

**CRITICAL: NETWORK TIER CLASSIFICATION**

For EVERY network switch/device, classify into ONE of these tiers:

🔵 BACKEND_FABRIC (Scale-Out/GPU-to-GPU Training Traffic):
   Visual Cues:
   - Thick cable lines (often blue, purple, or dark colors)
   - Labels: "IB", "InfiniBand", "NDR", "HDR", "400G", "800G", "Quantum", "Spectrum-X"
   - Large square connector icons (OSFP/QSFP112 ports)
   - High bandwidth annotations
   Topology:
   - Connects DIRECTLY to GPU/HCA ports on compute nodes
   - Often labeled as "Spine" or "Leaf" in Clos/Fat-Tree architecture
   - May show "Rail 0", "Rail 1" for multi-rail fabrics
   Hardware Hints:
   - NVIDIA Quantum series (InfiniBand)
   - NVIDIA Spectrum-X (RoCE/Ethernet RDMA)
   - Port count: typically 32-64 high-speed ports

🟢 FRONTEND_FABRIC (Tenant/Storage/North-South Traffic):
   Visual Cues:
   - Medium thickness cable lines (red, green, orange)
   - Labels: "ETH", "Ethernet", "100G", "200G", "Storage", "Data", "Client"
   - Medium square connector icons (QSFP/SFP+ ports)
   Topology:
   - Connects to storage nodes and server NICs (NOT HCAs)
   - Uplinks to data center core/aggregation layer
   - May be labeled "Frontend", "Data Network", "Storage Fabric"
   Hardware Hints:
   - Arista, Cisco, Juniper, or NVIDIA Spectrum switches
   - Port count: varies widely (24-128 ports)

🟡 OOB_MANAGEMENT (Out-of-Band/Control Plane):
   Visual Cues:
   - Thin lines or dashed lines (yellow, green, gray)
   - Labels: "MGT", "IPMI", "BMC", "Console", "OOB", "Management"
   - Small rectangular connector icons (RJ45/copper ports)
   - High port density (48+ ports)
   Topology:
   - Connects to the small "Mgmt", "BMC", or "IPMI" port on EVERY server
   - Connects to PDUs, KVMs, console servers
   - Physically separate network from production traffic
   Hardware Hints:
   - Standard enterprise switches (1G/10G copper)
   - Very high port density (48-96 ports per switch)

**OUTPUT REQUIREMENTS FOR NETWORK DEVICES:**

For EVERY switch detected, you MUST include:
1. network_tier: ("BACKEND_FABRIC" | "FRONTEND_FABRIC" | "OOB_MANAGEMENT")
2. protocol: ("InfiniBand" | "Ethernet" | "RoCE" | "Unknown")
3. link_speed_capability: ("800G" | "400G" | "200G" | "100G" | "10G" | "1G")
4. fabric_type: ("Compute_Fabric" | "Storage_Fabric" | "OOB_Mgmt")
5. port_count_detected: (count visible ports in the diagram)
6. connector_type: ("OSFP" | "QSFP" | "QSFP112" | "SFP+" | "RJ45" | "Unknown")
7. switch_role: ("spine" | "leaf" | "core" | "management" | "unknown")
8. confidence_score: (0.0-1.0 based on clarity of visual cues and labels)
9. evidence: (explain WHY you classified it this way - mention specific labels, cable colors, or topology)

**HIERARCHICAL LOCATION EXTRACTION:**

Extract hierarchical location data for DCIM compliance:
- Site: Data center site name (e.g., "DC-Austin", "Site-01", "Facility-A")
- Room: Server room or hall identifier (e.g., "Room-A", "Hall-2", "Floor-3")
- Row: Equipment row (e.g., "Row-1", "A", "R01")
- Rack: Rack identifier (e.g., "Rack-01", "A01", "Cabinet-5")
- U-Position: Rack unit position (e.g., "U10", "U20", "32")

**If location is shown as a combined string like "Rack-A01-U10" or "DC1-R3-A05-U12", parse it into separate components.**
**If some hierarchy levels are missing from the diagram, set them to null.**

**PORT DETECTION:**

For each device, identify visible ports:
- portLabel: The label shown in diagram (e.g., "P1", "eth0", "ib0", "HCA-1")
- portType: Infer from connector shape ("OSFP" | "QSFP" | "SFP+" | "RJ45" | "unknown")

Return a JSON array of devices in this exact format:
[
  {{
    "deviceName": "DGX-H100-01",
    "deviceType": "compute",
    "site": "DC-Austin",
    "room": "Hall-A",
    "row": "Row-1",
    "rack": "Rack-01",
    "uPosition": "U10",
    "position": {{"x": 25, "y": 30}},
    "ports": [
      {{"portLabel": "HCA-1", "portType": "OSFP"}},
      {{"portLabel": "NIC-1", "portType": "QSFP"}},
      {{"portLabel": "BMC", "portType": "RJ45"}}
    ]
  }},
  {{
    "deviceName": "IB-SPINE-01",
    "deviceType": "network",
    "network_tier": "BACKEND_FABRIC",
    "protocol": "InfiniBand",
    "link_speed_capability": "400G",
    "fabric_type": "Compute_Fabric",
    "port_count_detected": 64,
    "connector_type": "OSFP",
    "switch_role": "spine",
    "confidence_score": 0.95,
    "evidence": "Thick blue cables connecting to DGX HCA ports, labeled 'IB-400G', OSFP connector icons visible",
    "site": "DC-Austin",
    "room": "Hall-A",
    "row": "Row-1",
    "rack": "Rack-03",
    "uPosition": "U42",
    "position": {{"x": 75, "y": 30}},
    "ports": [
      {{"portLabel": "P1", "portType": "OSFP"}},
      {{"portLabel": "P2", "portType": "OSFP"}}
    ]
  }}
]

IMPORTANT: Return ONLY the JSON array, no additional text.
"""

    try:
        # Use centralized GeminiClient with generate_with_image method
        response_text = genai.generate_with_image(
            text_prompt=device_prompt,
            image_data=schematic_bytes,
            model='gemini-2.5-flash',
            mime_type='image/png'
        )
        
        # Parse response
        content = response_text
        
        # Extract JSON from response (sometimes the model includes markdown)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        devices_data = json.loads(content)
        
        # Store devices in Firestore
        firestore_client = get_firestore_client()
        
        for idx, device_data in enumerate(devices_data):
            device_id = f"device_{uuid.uuid4().hex[:12]}"
            
            device_doc = {
                "deviceId": device_id,
                "projectId": project_id,
                "deviceName": device_data.get("deviceName", f"Device-{idx}"),
                "deviceType": device_data.get("deviceType", "other"),
                # Hierarchical location (for DCIM-style matching)
                "site": device_data.get("site"),
                "room": device_data.get("room"),
                "row": device_data.get("row"),
                "rack": device_data.get("rack"),
                "uPosition": device_data.get("uPosition"),
                # Deprecated (kept for backward compatibility)
                "rackLocation": device_data.get("rack", "Unknown"),
                "position": device_data.get("position", {"x": 0, "y": 0}),
                "ports": device_data.get("ports", []),
                "metadata": device_data.get("metadata", {}),
                # Hardware details (populated from asset inventory CSV)
                "serialNumber": None,
                "assetTag": None,
                "manufacturer": None,
                "model": None,
                "macAddress": None,
                "purchaseDate": None,
                "warrantyExpiry": None,
                "verificationStatus": "pending",  # pending, verified, mismatch
                "extractedAt": firestore.SERVER_TIMESTAMP
            }
            
            get_scoped_collection(firestore_client, customer_id, "extracted_devices").document(device_id).set(device_doc)
        
        print(f"Extracted {len(devices_data)} devices")
        return devices_data
        
    except Exception as e:
        print(f"Device extraction failed: {str(e)}")
        raise


def extract_connections(
    schematic_bytes: bytes,
    color_legend: Dict[str, Any],
    devices: List[Dict[str, Any]],
    processing_config: Dict[str, Any],
    project_id: str,
    project_ref: Any,
    customer_id: str
) -> List[Dict[str, Any]]:
    """
    Use Gemini Vision API to extract connections between devices.
    """
    
    # Handle color_legend as both dict and list formats
    if isinstance(color_legend, list):
        # Convert list format to dict format
        legend_dict = {}
        for item in color_legend:
            if isinstance(item, dict) and 'color' in item:
                legend_dict[item['color']] = {
                    'connectionType': item.get('connectionType', 'Unknown'),
                    'bandwidth': item.get('bandwidth', 'Unknown')
                }
        color_legend = legend_dict
    
    # Build color legend description
    legend_desc = "\n".join([
        f"- {color}: {info['connectionType']} ({info['bandwidth']})"
        for color, info in color_legend.items()
    ])
    
    # Build device list for context
    device_list = "\n".join([
        f"- {d['deviceName']} ({d['deviceType']})"
        for d in devices
    ])
    
    connection_prompt = f"""
You are analyzing a data center schematic diagram for a GPU cluster. Extract ALL connections (cables/lines) between devices with network segment classification.

Color Legend (color to connection type mapping):
{legend_desc}

Devices in the diagram:
{device_list}

**NETWORK SEGMENT CLASSIFICATION:**

For each connection, classify the network segment based on visual cues and topology:

🔵 BACKEND_FABRIC (GPU-GPU Training Traffic):
   - Thick blue/purple cable lines
   - Connects GPU/HCA ports on compute nodes to InfiniBand switches
   - Labels: "IB", "InfiniBand", "NDR", "400G", "800G"
   - Large square connectors (OSFP/QSFP112)
   - Purpose: gpu-fabric, rdma, nccl

🟢 FRONTEND_FABRIC (Client/Storage Traffic):
   - Red/green/orange cable lines
   - Connects server NICs to Ethernet switches or storage nodes
   - Labels: "ETH", "Ethernet", "100G", "200G", "Storage"
   - Medium square connectors (QSFP/SFP+)
   - Purpose: tenant-access, storage-io, data-network

🟡 OOB_MANAGEMENT (Control Plane):
   - Thin/dashed yellow/green/gray lines
   - Connects BMC/IPMI ports to management switches
   - Labels: "MGT", "BMC", "IPMI", "OOB"
   - Small rectangular connectors (RJ45)
   - Purpose: management, monitoring, console

**PORT TYPE DETECTION:**

Look at the connector shape/size in the diagram:
- Large square connectors = OSFP (800G/400G InfiniBand)
- Medium square connectors = QSFP (100G/200G Ethernet)
- Small rectangular connectors = RJ45 (1G/10G Management)

**VALIDATION:**

Check if source and destination port types match:
- OSFP ↔ OSFP = compliant
- QSFP ↔ QSFP = compliant
- RJ45 ↔ RJ45 = compliant
- Mismatched types = port_mismatch

For each connection, provide:
1. sourceDevice - name of the source device (must match a device from the list above)
2. sourcePort - port label on source device
3. sourcePortType - port connector type ("OSFP" | "QSFP" | "RJ45" | "unknown")
4. destinationDevice - name of the destination device (must match a device from the list above)
5. destinationPort - port label on destination device
6. destinationPortType - port connector type ("OSFP" | "QSFP" | "RJ45" | "unknown")
7. connectionType - based on the line color (from the legend above)
8. bandwidth - bandwidth specification from the legend
9. segment - network tier ("BACKEND_FABRIC" | "FRONTEND_FABRIC" | "OOB_MANAGEMENT" | "UNKNOWN")
10. networkPurpose - purpose ("gpu-fabric" | "tenant-access" | "storage-io" | "management")
11. validationStatus - ("compliant" | "port_mismatch" | "tier_mismatch")
12. isTrunk - true if this appears to be a bundled/trunk connection (multiple parallel lines)
13. trunkSize - number of cables in the trunk (null if not a trunk)

Return a JSON array of connections in this exact format:
[
  {{
    "sourceDevice": "DGX-H100-01",
    "sourcePort": "HCA-1",
    "sourcePortType": "OSFP",
    "destinationDevice": "IB-SPINE-01",
    "destinationPort": "P1",
    "destinationPortType": "OSFP",
    "connectionType": "InfiniBand (NDR)",
    "bandwidth": "400G",
    "segment": "BACKEND_FABRIC",
    "networkPurpose": "gpu-fabric",
    "validationStatus": "compliant",
    "isTrunk": false,
    "trunkSize": null
  }},
  {{
    "sourceDevice": "Storage-01",
    "sourcePort": "NIC-1",
    "sourcePortType": "QSFP",
    "destinationDevice": "FE-Switch-01",
    "destinationPort": "P12",
    "destinationPortType": "QSFP",
    "connectionType": "Ethernet",
    "bandwidth": "100G",
    "segment": "FRONTEND_FABRIC",
    "networkPurpose": "storage-io",
    "validationStatus": "compliant",
    "isTrunk": false,
    "trunkSize": null
  }}
]

IMPORTANT: Return ONLY the JSON array, no additional text.
"""

    try:
        # Use centralized GeminiClient with generate_with_image method
        response_text = genai.generate_with_image(
            text_prompt=connection_prompt,
            image_data=schematic_bytes,
            model='gemini-2.5-flash',
            mime_type='image/png'
        )
        
        # Parse response
        content = response_text
        
        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        connections_data = json.loads(content)
        
        # Apply trunk expansion if enabled
        if processing_config.get("autoExpandTrunks", False):
            connections_data = expand_trunks(connections_data)
        
        # Store connections in Firestore
        firestore_client = get_firestore_client()
        
        for connection_data in connections_data:
            connection_id = f"conn_{uuid.uuid4().hex[:12]}"
            
            connection_doc = {
                "connectionId": connection_id,
                "projectId": project_id,
                "sourceDevice": connection_data.get("sourceDevice"),
                "sourcePort": connection_data.get("sourcePort"),
                "sourcePortType": connection_data.get("sourcePortType"),
                "destinationDevice": connection_data.get("destinationDevice"),
                "destinationPort": connection_data.get("destinationPort"),
                "destinationPortType": connection_data.get("destinationPortType"),
                "connectionType": connection_data.get("connectionType"),
                "bandwidth": connection_data.get("bandwidth"),
                "segment": connection_data.get("segment", "UNKNOWN"),
                "networkPurpose": connection_data.get("networkPurpose"),
                "validationStatus": connection_data.get("validationStatus", "compliant"),
                "isTrunk": connection_data.get("isTrunk", False),
                "trunkSize": connection_data.get("trunkSize")
            }
            
            get_scoped_collection(firestore_client, customer_id, "extracted_connections").document(connection_id).set(connection_doc)
        
        print(f"Extracted {len(connections_data)} connections")
        return connections_data
        
    except Exception as e:
        print(f"Connection extraction failed: {str(e)}")
        raise


def expand_trunks(connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Expand trunk connections into individual connections.
    """
    expanded = []
    
    for conn in connections:
        if conn.get("isTrunk") and conn.get("trunkSize"):
            # Expand trunk into individual connections
            trunk_size = conn["trunkSize"]
            for i in range(trunk_size):
                individual_conn = conn.copy()
                individual_conn["isTrunk"] = False
                individual_conn["trunkSize"] = None
                individual_conn["sourcePort"] = f"{conn['sourcePort']}-{i+1}"
                individual_conn["destinationPort"] = f"{conn['destinationPort']}-{i+1}"
                expanded.append(individual_conn)
        else:
            expanded.append(conn)
    
    return expanded


def validate_topology(
    devices: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
    processing_config: Dict[str, Any],
    project_id: str
) -> Dict[str, Any]:
    """
    Validate the extracted topology with enterprise-grade role-based validation.
    """
    critical_issues = []
    high_issues = []
    medium_issues = []
    warnings = []
    
    # === BASIC TOPOLOGY VALIDATION ===
    
    # Check for orphaned devices (no connections)
    device_names = {d["deviceName"] for d in devices}
    connected_devices = set()
    for conn in connections:
        connected_devices.add(conn["sourceDevice"])
        connected_devices.add(conn["destinationDevice"])
    
    orphaned = device_names - connected_devices
    if orphaned:
        warnings.append({
            "type": "orphaned_devices",
            "severity": "WARNING",
            "message": f"Found {len(orphaned)} devices with no connections",
            "devices": list(orphaned),
            "impact": "Unused equipment - may indicate missing cables or incomplete schematic"
        })
    
    # Check for invalid connections (devices not in device list)
    for conn in connections:
        if conn["sourceDevice"] not in device_names:
            critical_issues.append({
                "type": "invalid_source",
                "severity": "CRITICAL",
                "message": f"Connection references unknown source device: {conn['sourceDevice']}",
                "impact": "Data extraction error - schematic may be corrupted"
            })
        if conn["destinationDevice"] not in device_names:
            critical_issues.append({
                "type": "invalid_destination",
                "severity": "CRITICAL",
                "message": f"Connection references unknown destination device: {conn['destinationDevice']}",
                "impact": "Data extraction error - schematic may be corrupted"
            })
    
    # === NETWORK TIER VALIDATION ===
    
    network_tier_issues = validate_network_tiers(devices, connections)
    for issue in network_tier_issues:
        severity = issue.get("severity", "MEDIUM")
        if severity == "CRITICAL":
            critical_issues.append(issue)
        elif severity == "HIGH":
            high_issues.append(issue)
        else:
            medium_issues.append(issue)
    
    # === ROLE-BASED VALIDATION ===
    
    role_based_issues = validate_device_roles(devices, connections)
    for issue in role_based_issues:
        severity = issue.get("severity", "MEDIUM")
        if severity == "CRITICAL":
            critical_issues.append(issue)
        elif severity == "HIGH":
            high_issues.append(issue)
        else:
            medium_issues.append(issue)
    
    # === GPU RAIL VALIDATION (if enabled) ===
    
    if processing_config.get("validateRailAlignment", False):
        rail_issues = validate_gpu_rails(devices, connections)
        high_issues.extend(rail_issues)
    
    # === PORT COMPLIANCE VALIDATION ===
    
    port_compliance_issues = validate_port_compliance(connections)
    for issue in port_compliance_issues:
        severity = issue.get("severity", "HIGH")
        if severity == "CRITICAL":
            critical_issues.append(issue)
        elif severity == "HIGH":
            high_issues.append(issue)
        else:
            medium_issues.append(issue)
    
    # Combine all issues
    all_issues = critical_issues + high_issues + medium_issues
    
    # Create validation report
    validation_report = {
        "projectId": project_id,
        "totalDevices": len(devices),
        "totalConnections": len(connections),
        "criticalIssues": len(critical_issues),
        "highIssues": len(high_issues),
        "mediumIssues": len(medium_issues),
        "warnings": len(warnings),
        "criticalIssuesList": critical_issues,
        "highIssuesList": high_issues,
        "mediumIssuesList": medium_issues,
        "warningsList": warnings,
        "validatedAt": datetime.now().isoformat(),
        "passedValidation": len(critical_issues) == 0 and len(high_issues) == 0
    }
    
    # Store in Firestore
    firestore_client = get_firestore_client()
    report_id = f"validation_{uuid.uuid4().hex[:12]}"
    firestore_client.collection("validation_reports").document(report_id).set(validation_report)
    
    return validation_report


def validate_gpu_rails(devices: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate GPU rail alignment best practices.
    """
    issues = []
    
    # Get compute nodes
    compute_nodes = [d for d in devices if d["deviceType"] == "compute"]
    
    # Check each compute node has proper NVLink/InfiniBand connections
    for node in compute_nodes:
        node_name = node["deviceName"]
        
        # Find connections for this node
        node_connections = [
            c for c in connections
            if c["sourceDevice"] == node_name or c["destinationDevice"] == node_name
        ]
        
        # Check for InfiniBand connections
        ib_connections = [
            c for c in node_connections
            if "InfiniBand" in c.get("connectionType", "")
        ]
        
        if len(ib_connections) < 8:
            issues.append({
                "type": "insufficient_ib_rails",
                "severity": "HIGH",
                "message": f"{node_name} has only {len(ib_connections)} InfiniBand connections (recommended: 8 for GPU nodes)",
                "impact": "Reduced GPU-to-GPU bandwidth - will bottleneck distributed training"
            })
    
    return issues


def validate_network_tiers(devices: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate network tier classification and detect tier mismatches.
    
    Enterprise GPU clusters require strict network segmentation:
    - BACKEND_FABRIC: GPU-to-GPU traffic (InfiniBand/RoCE)
    - FRONTEND_FABRIC: Client/Storage traffic (Ethernet)
    - OOB_MANAGEMENT: Control plane (dedicated management network)
    
    Violations indicate:
    - Security boundary crossing
    - QoS policy conflicts
    - Performance degradation
    """
    issues = []
    
    # Build device lookup with network metadata
    device_lookup = {d["deviceName"]: d for d in devices}
    
    # Check each connection for tier compliance
    for conn in connections:
        source_device = device_lookup.get(conn["sourceDevice"])
        dest_device = device_lookup.get(conn["destinationDevice"])
        
        if not source_device or not dest_device:
            continue
        
        # Get network tiers from device metadata
        source_tier = None
        dest_tier = None
        conn_segment = conn.get("segment", "UNKNOWN")
        
        if source_device.get("networkMetadata"):
            source_tier = source_device["networkMetadata"].get("tier")
        if dest_device.get("networkMetadata"):
            dest_tier = dest_device["networkMetadata"].get("tier")
        
        # === RULE 1: Backend Fabric Purity ===
        # Backend fabric switches should ONLY connect to other backend devices
        if source_tier == "BACKEND_FABRIC" and dest_tier and dest_tier != "BACKEND_FABRIC":
            issues.append({
                "type": "tier_mismatch_backend_contamination",
                "severity": "CRITICAL",
                "message": f"BACKEND_FABRIC switch '{conn['sourceDevice']}' connected to {dest_tier} device '{conn['destinationDevice']}'",
                "impact": "Security boundary violation - GPU fabric contaminated with non-RDMA traffic",
                "recommendation": "Physically separate backend fabric from frontend/OOB networks"
            })
        
        if dest_tier == "BACKEND_FABRIC" and source_tier and source_tier != "BACKEND_FABRIC":
            issues.append({
                "type": "tier_mismatch_backend_contamination",
                "severity": "CRITICAL",
                "message": f"BACKEND_FABRIC switch '{conn['destinationDevice']}' connected to {source_tier} device '{conn['sourceDevice']}'",
                "impact": "Security boundary violation - GPU fabric contaminated with non-RDMA traffic",
                "recommendation": "Physically separate backend fabric from frontend/OOB networks"
            })
        
        # === RULE 2: OOB Management Isolation ===
        # OOB management switches should ONLY connect to BMC/IPMI ports
        if source_tier == "OOB_MANAGEMENT" and conn_segment != "OOB_MANAGEMENT":
            issues.append({
                "type": "tier_mismatch_oob_breach",
                "severity": "HIGH",
                "message": f"OOB_MANAGEMENT switch '{conn['sourceDevice']}' carrying {conn_segment} traffic",
                "impact": "Management network security breach - production traffic on control plane",
                "recommendation": "Route all non-BMC traffic through frontend fabric"
            })
        
        if dest_tier == "OOB_MANAGEMENT" and conn_segment != "OOB_MANAGEMENT":
            issues.append({
                "type": "tier_mismatch_oob_breach",
                "severity": "HIGH",
                "message": f"OOB_MANAGEMENT switch '{conn['destinationDevice']}' carrying {conn_segment} traffic",
                "impact": "Management network security breach - production traffic on control plane",
                "recommendation": "Route all non-BMC traffic through frontend fabric"
            })
        
        # === RULE 3: Connection Segment Consistency ===
        # Connection segment should match device tiers
        if source_tier and conn_segment != "UNKNOWN" and source_tier != conn_segment:
            issues.append({
                "type": "tier_segment_mismatch",
                "severity": "MEDIUM",
                "message": f"Device '{conn['sourceDevice']}' is {source_tier} but connection is {conn_segment}",
                "impact": "Labeling inconsistency - may cause QoS policy misapplication",
                "recommendation": "Verify color legend and re-extract schematic"
            })
    
    return issues


def validate_device_roles(devices: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate device roles and ensure proper network architecture.
    
    Best Practices:
    - Compute nodes: Should have Backend (HCA) + Frontend (NIC) + OOB (BMC) connections
    - Storage nodes: Should have Frontend (NIC) + OOB (BMC) connections
    - Spine switches: Should connect to Leaf switches (uplinks) and possibly other Spines (ISL)
    - Leaf switches: Should connect to servers (downlinks) and Spine switches (uplinks)
    """
    issues = []
    
    # Build connection lookup
    device_connections = {}
    for device in devices:
        device_name = device["deviceName"]
        device_connections[device_name] = [
            c for c in connections
            if c["sourceDevice"] == device_name or c["destinationDevice"] == device_name
        ]
    
    for device in devices:
        device_name = device["deviceName"]
        device_type = device.get("deviceType")
        conns = device_connections.get(device_name, [])
        
        # === COMPUTE NODE VALIDATION ===
        if device_type == "compute":
            # Segment breakdown
            backend_conns = [c for c in conns if c.get("segment") == "BACKEND_FABRIC"]
            frontend_conns = [c for c in conns if c.get("segment") == "FRONTEND_FABRIC"]
            oob_conns = [c for c in conns if c.get("segment") == "OOB_MANAGEMENT"]
            
            # Check for backend fabric (GPU interconnect)
            if len(backend_conns) == 0:
                issues.append({
                    "type": "missing_backend_fabric",
                    "severity": "CRITICAL",
                    "message": f"Compute node '{device_name}' has NO backend fabric connections",
                    "impact": "GPU node cannot participate in distributed training - no RDMA fabric",
                    "recommendation": "Connect HCA ports to InfiniBand/RoCE switches"
                })
            elif len(backend_conns) < 4:
                issues.append({
                    "type": "insufficient_backend_bandwidth",
                    "severity": "HIGH",
                    "message": f"Compute node '{device_name}' has only {len(backend_conns)} backend connections (recommended: 8)",
                    "impact": "Reduced GPU-to-GPU bandwidth - training performance degradation",
                    "recommendation": "Add more HCA connections for multi-rail NCCL topology"
                })
            
            # Check for OOB management
            if len(oob_conns) == 0:
                issues.append({
                    "type": "missing_oob_management",
                    "severity": "MEDIUM",
                    "message": f"Compute node '{device_name}' has NO OOB management connection",
                    "impact": "Cannot remotely power-cycle or access BIOS if node hangs",
                    "recommendation": "Connect BMC port to management switch"
                })
        
        # === STORAGE NODE VALIDATION ===
        elif device_type == "storage":
            frontend_conns = [c for c in conns if c.get("segment") == "FRONTEND_FABRIC"]
            
            if len(frontend_conns) == 0:
                issues.append({
                    "type": "storage_unreachable",
                    "severity": "CRITICAL",
                    "message": f"Storage node '{device_name}' has NO frontend network connections",
                    "impact": "Storage inaccessible to compute nodes - jobs will fail",
                    "recommendation": "Connect storage NICs to frontend Ethernet switches"
                })
        
        # === NETWORK SWITCH VALIDATION ===
        elif device_type in ["network", "switch-spine", "switch-leaf"]:
            network_meta = device.get("networkMetadata", {})
            switch_role = network_meta.get("switchRole")
            tier = network_meta.get("tier")
            
            # Spine switches should have uplinks and downlinks
            if switch_role == "spine":
                # Count peer connections (to other spines) and leaf connections
                peer_conns = [c for c in conns if "spine" in c.get("sourceDevice", "").lower() or "spine" in c.get("destinationDevice", "").lower()]
                leaf_conns = [c for c in conns if "leaf" in c.get("sourceDevice", "").lower() or "leaf" in c.get("destinationDevice", "").lower()]
                
                if len(leaf_conns) == 0:
                    issues.append({
                        "type": "spine_no_leafs",
                        "severity": "CRITICAL",
                        "message": f"Spine switch '{device_name}' has NO connections to leaf switches",
                        "impact": "Spine switch is isolated - Clos fabric broken",
                        "recommendation": "Connect spine uplinks to all leaf switches for full bisection bandwidth"
                    })
            
            # Leaf switches should connect to servers and spines
            if switch_role == "leaf":
                server_conns = [c for c in conns if c.get("sourceDevice") != device_name and ("compute" in c.get("sourceDevice", "").lower() or "storage" in c.get("sourceDevice", "").lower()) or c.get("destinationDevice") != device_name and ("compute" in c.get("destinationDevice", "").lower() or "storage" in c.get("destinationDevice", "").lower())]
                spine_conns = [c for c in conns if "spine" in c.get("sourceDevice", "").lower() or "spine" in c.get("destinationDevice", "").lower()]
                
                if len(server_conns) == 0:
                    issues.append({
                        "type": "leaf_no_servers",
                        "severity": "HIGH",
                        "message": f"Leaf switch '{device_name}' has NO server connections",
                        "impact": "Leaf switch not serving any compute/storage nodes",
                        "recommendation": "Connect leaf downlinks to server HCAs/NICs"
                    })
                
                if len(spine_conns) == 0:
                    issues.append({
                        "type": "leaf_no_spines",
                        "severity": "CRITICAL",
                        "message": f"Leaf switch '{device_name}' has NO uplinks to spine layer",
                        "impact": "Leaf switch isolated - no inter-rack traffic possible",
                        "recommendation": "Connect leaf uplinks to all spine switches"
                    })
    
    return issues


def validate_port_compliance(connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate port type compliance (connector matching).
    
    Physical Layer Rules:
    - OSFP ↔ OSFP: Compliant (400G/800G InfiniBand)
    - QSFP ↔ QSFP: Compliant (100G/200G Ethernet)
    - RJ45 ↔ RJ45: Compliant (1G/10G Management)
    - Mismatched connectors: Physical impossibility or requires adapter
    """
    issues = []
    
    for conn in connections:
        source_port_type = conn.get("sourcePortType", "unknown")
        dest_port_type = conn.get("destinationPortType", "unknown")
        validation_status = conn.get("validationStatus", "compliant")
        
        # Port type mismatch
        if source_port_type != "unknown" and dest_port_type != "unknown" and source_port_type != dest_port_type:
            issues.append({
                "type": "port_type_mismatch",
                "severity": "HIGH",
                "message": f"Port mismatch: {conn['sourceDevice']}[{conn['sourcePort']}] ({source_port_type}) ↔ {conn['destinationDevice']}[{conn['destinationPort']}] ({dest_port_type})",
                "impact": "Physical connector incompatibility - cable cannot be plugged in without adapter",
                "recommendation": "Verify schematic accuracy or use breakout cables if intentional"
            })
        
        # If Gemini already flagged a validation issue
        if validation_status == "port_mismatch":
            issues.append({
                "type": "ai_detected_port_mismatch",
                "severity": "HIGH",
                "message": f"AI-detected port mismatch: {conn['sourceDevice']}[{conn['sourcePort']}] ↔ {conn['destinationDevice']}[{conn['destinationPort']}]",
                "impact": "Schematic shows incompatible port types",
                "recommendation": "Review schematic and color legend configuration"
            })
        
        if validation_status == "tier_mismatch":
            issues.append({
                "type": "ai_detected_tier_mismatch",
                "severity": "MEDIUM",
                "message": f"AI-detected tier mismatch: {conn['sourceDevice']} ↔ {conn['destinationDevice']}",
                "impact": "Connection crosses network tier boundaries",
                "recommendation": "Verify this is intentional (e.g., uplink to aggregation layer)"
            })
    
    return issues
