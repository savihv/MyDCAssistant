"""Test Data Setup for Day 1 Provisioning

Creates mock Firestore data to simulate the complete DHCP provisioning workflow
without requiring physical switches or a real data center environment.

This script populates:
1. Cluster bringup project metadata
2. Extracted devices from "Day 0" schematic analysis
3. Live infrastructure records (devices that have powered on)

Test Scenarios Created:
- Perfect Match: MAC + Serial match → IP assigned
- Identity Mismatch: MAC matches but wrong serial → BLOCKED
- Unknown Device: MAC not in inventory → Alert created
- Unreachable: Switch boots but doesn't respond to serial query

Usage:
    from app.libs.test_data_setup import setup_test_project
    
    project_id = setup_test_project()
    print(f"Test project created: {project_id}")
"""

from google.cloud import firestore  # type: ignore
from datetime import datetime
import uuid


def setup_test_project() -> str:
    """
    Create a complete test project with Day 0 devices and MAC mappings.
    
    Returns:
        project_id: The created project ID (format: bringup_XXXXXXXXXXXX)
    
    Example:
        >>> project_id = setup_test_project()
        >>> print(project_id)  # "bringup_a1b2c3d4e5f6"
    """
    firestore_client = firestore.Client()
    project_id = f"bringup_{uuid.uuid4().hex[:12]}"
    
    print(f"\n{'='*70}")
    print(f"  🧪 CREATING TEST PROJECT: {project_id}")
    print(f"{'='*70}\n")
    
    # Create project document
    project_doc = {
        "projectId": project_id,
        "projectName": "Day 1 Provisioning Test Project",
        "status": "completed",
        "createdAt": datetime.utcnow(),
        "schematicFilename": "test_cluster_schematic.png",
        "description": "Simulated GPU cluster for testing Day 1 DHCP provisioning",
        "colorLegend": {},
        "deviceConventions": {},
        "processingConfig": {},
        "progressPercentage": 100,
        "currentStage": "completed"
    }
    
    firestore_client.collection("cluster_bringup_projects").document(project_id).set(project_doc)
    print(f"✅ Project created: {project_id}")
    
    # Create test devices (Day 0 inventory from schematic extraction)
    devices = _create_test_devices(firestore_client, project_id)
    print(f"✅ Created {len(devices)} Day 0 devices")
    
    # Create MAC-to-device mappings for DHCP scraper
    mappings = _create_mac_mappings(firestore_client, project_id, devices)
    print(f"✅ Created {len(mappings)} MAC address mappings")
    
    print(f"\n{'='*70}")
    print("  ✅ TEST PROJECT READY")
    print(f"{'='*70}")
    print(f"\nProject ID: {project_id}")
    print("\nTest Scenarios Available:")
    print("  1. Perfect Match:     MAC 00:1B:21:D9:56:E1 (IB-SPINE-01)")
    print("  2. Perfect Match:     MAC 00:1B:21:D9:56:E2 (IB-LEAF-01)")
    print("  3. Perfect Match:     MAC 00:1B:21:D9:56:E3 (FE-SWITCH-01)")
    print("  4. Identity Mismatch: MAC 00:1B:21:D9:56:E4 (Wrong serial)")
    print("  5. Unknown Device:    MAC FF:FF:FF:FF:FF:FF (Not in inventory)")
    print("\nNext Steps:")
    print("  from app.libs.dhcp_simulator import simulate_discovery")
    print(f"  simulate_discovery(project_id='{project_id}', mac='00:1B:21:D9:56:E1')\n")
    
    return project_id


def _create_test_devices(firestore_client: firestore.Client, project_id: str) -> list:
    """
    Create Day 0 devices extracted from schematic.
    
    These represent the "planned" hardware inventory that Installation
    Leads expect to find at each rack location.
    """
    devices = [
        {
            "deviceId": f"dev_{uuid.uuid4().hex[:8]}",
            "deviceName": "IB-SPINE-01",
            "deviceType": "IB_Spine",
            "projectId": project_id,
            "rackLocation": "Rack-01/U42",
            "location": {
                "site": "DC-Austin",
                "room": "Hall-A",
                "row": "Row-1",
                "rack": "Rack-01",
                "uPosition": "U42"
            },
            "hardware_info": {
                "manufacturer": "NVIDIA",
                "model": "Quantum-2 QM9700",
                "serial_number": "SNIB-SPINE-01-SERIAL",
                "asset_tag": "TAG-IB-SPINE-01",
                "mac_address": "00:1B:21:D9:56:E1"
            },
            "network_metadata": {
                "tier": "BACKEND_FABRIC",
                "protocol": "InfiniBand",
                "link_speed_capability": "400G",
                "switch_role": "spine",
                "port_count_detected": 64
            },
            "expected_ip": "10.0.1.50",
            "createdAt": datetime.utcnow()
        },
        {
            "deviceId": f"dev_{uuid.uuid4().hex[:8]}",
            "deviceName": "IB-LEAF-01",
            "deviceType": "IB_Leaf",
            "projectId": project_id,
            "rackLocation": "Rack-02/U38",
            "location": {
                "site": "DC-Austin",
                "room": "Hall-A",
                "row": "Row-1",
                "rack": "Rack-02",
                "uPosition": "U38"
            },
            "hardware_info": {
                "manufacturer": "NVIDIA",
                "model": "Quantum-2 QM9700",
                "serial_number": "SNIB-LEAF-01-SERIAL",
                "asset_tag": "TAG-IB-LEAF-01",
                "mac_address": "00:1B:21:D9:56:E2"
            },
            "network_metadata": {
                "tier": "BACKEND_FABRIC",
                "protocol": "InfiniBand",
                "link_speed_capability": "400G",
                "switch_role": "leaf",
                "port_count_detected": 64
            },
            "expected_ip": "10.0.1.51",
            "createdAt": datetime.utcnow()
        },
        {
            "deviceId": f"dev_{uuid.uuid4().hex[:8]}",
            "deviceName": "FE-SWITCH-01",
            "deviceType": "FE_Switch",
            "projectId": project_id,
            "rackLocation": "Rack-03/U42",
            "location": {
                "site": "DC-Austin",
                "room": "Hall-A",
                "row": "Row-1",
                "rack": "Rack-03",
                "uPosition": "U42"
            },
            "hardware_info": {
                "manufacturer": "Arista",
                "model": "7280SR3-48YC8",
                "serial_number": "SNFE-SW-01-SERIAL",
                "asset_tag": "TAG-FE-SW-01",
                "mac_address": "00:1B:21:D9:56:E3"
            },
            "network_metadata": {
                "tier": "FRONTEND_FABRIC",
                "protocol": "Ethernet",
                "link_speed_capability": "100G",
                "switch_role": "leaf",
                "port_count_detected": 48
            },
            "expected_ip": "10.0.2.10",
            "createdAt": datetime.utcnow()
        },
        {
            "deviceId": f"dev_{uuid.uuid4().hex[:8]}",
            "deviceName": "IB-SPINE-02",
            "deviceType": "IB_Spine",
            "projectId": project_id,
            "rackLocation": "Rack-01/U38",
            "location": {
                "site": "DC-Austin",
                "room": "Hall-A",
                "row": "Row-1",
                "rack": "Rack-01",
                "uPosition": "U38"
            },
            "hardware_info": {
                "manufacturer": "NVIDIA",
                "model": "Quantum-2 QM9700",
                "serial_number": "SNIB-SPINE-02-SERIAL",
                "asset_tag": "TAG-IB-SPINE-02",
                "mac_address": "00:1B:21:D9:56:E4"  # This one will have wrong serial in test
            },
            "network_metadata": {
                "tier": "BACKEND_FABRIC",
                "protocol": "InfiniBand",
                "link_speed_capability": "400G",
                "switch_role": "spine",
                "port_count_detected": 64
            },
            "expected_ip": "10.0.1.52",
            "createdAt": datetime.utcnow()
        }
    ]
    
    # Store devices in Firestore
    for device in devices:
        device_id = device["deviceId"]
        firestore_client.collection("extracted_devices").document(device_id).set(device)
    
    return devices


def _create_mac_mappings(firestore_client: firestore.Client, project_id: str, devices: list) -> list:
    """
    Create MAC-to-serial mappings in live_infrastructure collection.
    
    This simulates what the DHCP scraper would discover during actual
    switch power-on events.
    """
    mappings = []
    
    # Create mappings for devices (simulating DHCP scraper results)
    for device in devices:
        mac = device["hardware_info"]["mac_address"]
        
        # Simulate different scenarios
        if mac == "00:1B:21:D9:56:E4":
            # SCENARIO: Identity Mismatch
            # MAC matches but serial is WRONG (simulates swapped hardware)
            detected_serial = "SNIB-SPINE-WRONG-999"
            status = "PENDING"  # Will be set to BLOCKED when scraper runs
        else:
            # SCENARIO: Perfect Match
            detected_serial = device["hardware_info"]["serial_number"]
            status = "PENDING"  # Will be set to PROVISIONED when scraper runs
        
        mapping = {
            "projectId": project_id,
            "macAddress": mac,
            "deviceName": device["deviceName"],
            "location": device["location"],
            "expectedSerial": device["hardware_info"]["serial_number"],
            "detectedSerial": detected_serial,
            "status": status,
            "identityVerified": False,
            "serialNumberMatch": detected_serial == device["hardware_info"]["serial_number"],
            "assignedIp": None,
            "createdAt": datetime.utcnow()
        }
        
        # Store in live_infrastructure collection
        doc_id = f"{project_id}_{mac.replace(':', '_')}"
        firestore_client.collection("live_infrastructure").document(doc_id).set(mapping)
        mappings.append(mapping)
    
    return mappings


def cleanup_test_project(project_id: str):
    """
    Remove all test data for a project.
    
    Args:
        project_id: The project ID to clean up
    
    Example:
        >>> cleanup_test_project("bringup_abc123")
        ✅ Cleaned up test project: bringup_abc123
    """
    firestore_client = firestore.Client()
    
    print(f"\n🧽 Cleaning up test project: {project_id}")
    
    # Delete project document
    firestore_client.collection("cluster_bringup_projects").document(project_id).delete()
    
    # Delete devices
    devices = firestore_client.collection("extracted_devices").where("projectId", "==", project_id).stream()
    for doc in devices:
        doc.reference.delete()
    
    # Delete live infrastructure
    live_infra = firestore_client.collection("live_infrastructure").where("projectId", "==", project_id).stream()
    for doc in live_infra:
        doc.reference.delete()
    
    # Delete alerts
    alerts = firestore_client.collection("provisioning_alerts").where("projectId", "==", project_id).stream()
    for doc in alerts:
        doc.reference.delete()
    
    print(f"✅ Cleaned up test project: {project_id}\n")


if __name__ == "__main__":
    # Example usage when run directly
    project_id = setup_test_project()
    
    print("\n" + "="*70)
    print("  🧪 READY TO TEST")
    print("="*70)
    print("\nRun simulations with:")
    print("  from app.libs.dhcp_simulator import simulate_discovery")
    print(f"  simulate_discovery(project_id='{project_id}', mac='00:1B:21:D9:56:E1')\n")
