"""Zero-Touch Provisioning (ZTP) API Endpoints

Two-stage provisioning workflow:
1. Discovery Stage: Switch reports serial number via callback
2. Configuration Stage: Switch downloads full config script

This avoids the "Pre-ZTP Connectivity Paradox" where fresh switches
have no SSH/SNMP enabled for remote serial queries.

Workflow:
    Switch Powers On → DHCP DISCOVER → DHCPScraper generates discovery script →
    Switch executes discovery script → Reports serial to /ztp/discovery →
    API verifies identity → Generates full ZTP config →
    Switch downloads config from /ztp/config/{mac} → Auto-configures

Example Discovery Script (sent via DHCP Option 67):
    #!/bin/bash
    SERIAL=$(dmidecode -s system-serial-number)
    curl -X POST https://yourapp.com/ztp/discovery \\
      -d '{"mac":"00:1B:...","serial":"NVDA-QM9700-SP01-2024"}'
"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from google.cloud import firestore  # type: ignore
import json
from google.oauth2 import service_account

from app.libs.dhcp_scraper import DHCPScraper
from app.libs.firestore_scoping import get_scoped_collection

router = APIRouter()

# Initialize Firestore client
def get_firestore_client():
    """Get Firestore client with credentials from environment."""
    credentials_json = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
    if credentials_json:
        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        return firestore.Client(credentials=credentials)
    return firestore.Client()

def get_project_id() -> str:
    """Get cluster project ID from environment or default."""
    return os.environ.get("CLUSTER_PROJECT_ID", "default-cluster")


def get_customer_id() -> str:
    """Get customer ID from request context or default.
    
    In production, this would be extracted from authenticated request.
    For now, defaults to 'default' for backward compatibility.
    """
    # TODO: Extract from Stack Auth JWT or request header in production
    return os.environ.get("CUSTOMER_ID", "default")


class DiscoveryReport(BaseModel):
    """Switch identity report from discovery script."""
    mac: str  # MAC address (e.g., "00:1B:21:D9:56:E3")
    serial: str  # Serial number (e.g., "NVDA-QM9700-SP01-2024")
    vendor: Optional[str] = None  # Optional: Extracted from dmidecode
    model: Optional[str] = None  # Optional: Extracted from dmidecode
    switch_id: Optional[str] = None  # Optional: Planned device name


class DiscoveryResponse(BaseModel):
    """Response to discovery callback."""
    status: str  # "VERIFIED" | "MISMATCH" | "UNKNOWN"
    message: str
    next_step: str  # URL to download full config
    device_name: Optional[str] = None
    assigned_ip: Optional[str] = None
    alert_id: Optional[str] = None


class ConfigScriptResponse(BaseModel):
    """Full ZTP configuration script."""
    script: str  # Bash script content
    device_name: str
    vendor: str
    model: str
    status: str


class LLDPNeighbor(BaseModel):
    """LLDP neighbor information from switch."""
    port_id: str  # "Ethernet1/1", "p1", "et-0/0/1"
    neighbor_hostname: str  # "B200-Rack01-Srv03-GPU2-HCA0"
    neighbor_description: Optional[str] = None
    neighbor_mac: Optional[str] = None


class CablingValidationRequest(BaseModel):
    """Request to validate cabling against topology expectations."""
    switch_id: str  # "IB-LEAF-P0-L01"
    plane_id: int  # 0-indexed plane ID
    leaf_id: int  # 0-indexed leaf ID within plane
    neighbors: list[LLDPNeighbor]  # LLDP neighbor data


class PortValidationResultModel(BaseModel):
    """Validation result for a single port."""
    port_id: str
    port_number: int
    status: str  # "PASS", "FAIL", "MISSING"
    expected_neighbor: Optional[str]
    actual_neighbor: Optional[str]
    mismatch_details: Optional[str] = None
    swap_recommendation: Optional[str] = None


class RailViolationModel(BaseModel):
    """Rail isolation violation for cross-plane cabling."""
    port_id: str
    expected_plane: int
    actual_tail: Optional[int]  # None if unparseable
    neighbor_hostname: str
    severity: str  # "CRITICAL"
    violation_type: str  # "RAIL_CONTAMINATION" or "UNKNOWN_TAIL"
    impact: str
    action: str


class SUBoundaryViolationModel(BaseModel):
    """SU boundary violation for cross-SU cabling.
    
    This represents a CRITICAL systemic deployment error where a switch
    meant for one Scalable Unit is cabled to devices in another SU.
    Unlike rail violations (localized mis-wires), SU breaches indicate
    wrong rack placement or switch role confusion.
    """
    port_id: str
    neighbor_hostname: str
    expected_su_id: int
    actual_su_id: int
    severity: str = "CRITICAL"
    violation_type: str  # "CROSS_SU_CONTAMINATION" or "SU_PARSE_FAILURE"
    impact: str
    action: str


class CablingValidationResponse(BaseModel):
    """Complete cabling validation report."""
    status: str  # "COMPLETE"
    switch_id: str
    plane_id: int
    leaf_id: int
    cluster_healthy: bool
    total_ports: int
    passed: int
    failed: int
    missing: int
    health_percentage: float
    results: list[PortValidationResultModel]
    swap_recommendations: list[str]
    rail_violations: list[RailViolationModel] = []  # Rail contamination
    has_rail_contamination: bool = False  # Quick check flag
    su_violations: list[SUBoundaryViolationModel] = []  # NEW: SU boundary breaches
    has_su_contamination: bool = False  # NEW: Priority triage flag


@router.post("/ztp/discovery", response_model=DiscoveryResponse)
def handle_discovery_callback(body: DiscoveryReport):
    """Stage 1: Receive serial number report from switch.
    
    Called by discovery script running on switch during initial boot.
    Verifies hardware identity and prepares full ZTP configuration.
    
    Args:
        body: Discovery report with MAC, serial, and optional vendor/model
        
    Returns:
        Discovery response with verification status and next steps
        
    Example Request:
        POST /ztp/discovery
        {
            "mac": "00:1B:21:D9:56:E3",
            "serial": "NVDA-QM9700-SP01-2024",
            "vendor": "NVIDIA",
            "model": "QM9700"
        }
        
    Example Response (Success):
        {
            "status": "VERIFIED",
            "message": "Identity verified. Ready for configuration.",
            "next_step": "https://yourapp.com/ztp/config/00:1B:21:D9:56:E3",
            "device_name": "IB-SPINE-01",
            "assigned_ip": "10.0.4.250"
        }
    """
    print(f"\n{'='*70}")
    print("📡 DISCOVERY CALLBACK RECEIVED")
    print(f"   MAC: {body.mac}")
    print(f"   Serial: {body.serial}")
    print(f"   Vendor/Model: {body.vendor} {body.model}")
    print(f"{'='*70}")
    
    # TODO: Extract customer_id from auth context or webhook URL path
    # For now, use default customer for backward compatibility
    customer_id = "default"
    
    scraper = DHCPScraper(project_id=get_project_id(), customer_id=customer_id)
    
    # Use the new discovery callback handler
    result = scraper.handle_discovery_callback(
        mac_address=body.mac,
        detected_serial=body.serial,
        vendor=body.vendor,
        model=body.model
    )
    
    # Map result to response
    status = result.get("status")
    
    if status == "SUCCESS":
        return DiscoveryResponse(
            status="VERIFIED",
            message="Identity verified. Full configuration ready.",
            next_step=f"/api/ztp/config/{body.mac}",
            device_name=result.get("device_name"),
            assigned_ip=result.get("assigned_ip")
        )
    elif status == "BLOCKED":
        return DiscoveryResponse(
            status="MISMATCH",
            message=f"Identity mismatch: {result.get('reason')}",
            next_step="/api/provisioning-alerts",  # Lead should review alerts
            alert_id=result.get("alert_id")
        )
    else:
        return DiscoveryResponse(
            status="UNKNOWN",
            message="Device not found in inventory.",
            next_step="/api/provisioning-alerts"
        )


@router.get("/ztp/config/{mac_address}")
def get_full_ztp_config(mac_address: str):
    """Stage 2: Provide full configuration script to verified switch.
    
    Called by switch after identity verification succeeds.
    Returns vendor-specific configuration script with all port IPs.
    
    Args:
        mac_address: MAC address of verified switch
        
    Returns:
        ConfigScriptResponse with bash script content
        
    Raises:
        HTTPException: If switch not verified or config not ready
        
    Example Request:
        GET /ztp/config/00:1B:21:D9:56:E3
        
    Example Response:
        {
            "script": "#!/bin/bash\ncli\nconfigure terminal\n...",
            "device_name": "IB-SPINE-01",
            "vendor": "NVIDIA",
            "model": "QM9700",
            "status": "READY"
        }
    """
    print(f"\n📥 CONFIG DOWNLOAD REQUEST: MAC {mac_address}")
    
    # Normalize MAC address
    mac_normalized = mac_address.upper().replace("-", ":").replace(".", ":")
    
    # Query Firestore for provisioned device
    firestore_client = get_firestore_client()
    customer_id = get_customer_id()
    
    # Search live_infrastructure for device with DISCOVERY_VERIFIED status
    query = get_scoped_collection(firestore_client, customer_id, "live_infrastructure").where(
        "macAddress", "==", mac_normalized
    ).where(
        "status", "==", "DISCOVERY_VERIFIED"
    ).limit(1)
    
    results = list(query.stream())
    
    if not results:
        print(f"❌ No verified device found for MAC {mac_normalized}")
        raise HTTPException(
            status_code=404,
            detail="Device not verified or configuration not ready. Complete discovery stage first."
        )
    
    device_doc = results[0].to_dict()
    
    # Check if ZTP script URL exists
    ztp_url = device_doc.get("ztpUrl")
    ztp_storage_key = device_doc.get("ztpStorageKey")
    
    if not ztp_storage_key:
        print(f"❌ No ZTP script found for {device_doc.get('deviceName')}")
        raise HTTPException(
            status_code=500,
            detail="Configuration script not generated. Contact administrator."
        )
    
    # Load script from storage
    import databutton as db
    
    try:
        script_data = db.storage.json.get(ztp_storage_key)
        script_content = script_data.get("script_content", "")
        
        print(f"✅ Serving ZTP config for {device_doc.get('deviceName')}")
        print(f"   Vendor: {device_doc.get('vendor')} {device_doc.get('model')}")
        print(f"   Script Size: {len(script_content)} bytes")
        
        # Return as plain text script (not JSON)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(
            content=script_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={device_doc.get('deviceName')}.sh"
            }
        )
        
    except Exception as e:
        print(f"❌ Error loading script: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load configuration script: {str(e)}"
        )


@router.get("/ztp/discovery-script/{mac_address}")
def get_discovery_script(mac_address: str):
    """Generate minimal discovery script for unconfigured switch.
    
    This is the initial script sent via DHCP Option 67 that extracts
    the serial number and reports it back to the API.
    
    Args:
        mac_address: MAC address of switch (from DHCP request)
        
    Returns:
        Bash script as plain text
        
    Example Response:
        #!/bin/bash
        SERIAL=$(dmidecode -s system-serial-number)
        curl -X POST https://yourapp.com/ztp/discovery \\
          -d '{"mac":"00:1B:...","serial":"$SERIAL"}'
    """
    from fastapi.responses import PlainTextResponse
    from app.libs.jit_ztp_generator import JITZTPGenerator
    
    # Get base URL for callbacks
    base_url = os.environ.get("APP_BASE_URL", "https://juniortechbot.riff.works/techassist")
    callback_url = f"{base_url}/api/ztp/discovery"
    
    generator = JITZTPGenerator()
    script = generator.generate_discovery_script(
        mac_address=mac_address,
        callback_url=callback_url
    )
    
    print(f"📤 Serving discovery script for MAC {mac_address}")
    
    return PlainTextResponse(
        content=script,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=discovery_{mac_address}.sh"
        }
    )


@router.post("/validate-cabling", response_model=CablingValidationResponse)
def validate_cabling(body: CablingValidationRequest):
    """Validate physical cabling against GPU-aware topology expectations.
    
    This is the critical "Verification" phase. After the switch executes its ZTP
    configuration and enables LLDP, it reports what neighbors it actually sees.
    We compare this against the expected GPU-to-Leaf mapping to detect mis-wires.
    
    **Why This Matters:**
    In a 4K GPU cluster with 32,768 cables, a single mis-wire causes:
    - ❌ 15-40% degradation in All-Reduce operations
    - ❌ Cross-plane traffic (defeats InfiniBand rail isolation)
    - ❌ Discovered only during expensive training runs ($50K+ delay)
    
    **This API Prevents:**
    - Wrong cables (Port 1 has Port 2's GPU)
    - Cross-rack errors (Rack 1 GPU on Rack 2 port)
    - Missing cables (expected connection, but no LLDP neighbor)
    
    Args:
        body: Cabling validation request with switch ID and LLDP neighbor list
        
    Returns:
        Validation report with per-port status and health percentage
        
    Example Request:
        POST /validate-cabling
        {
            "switch_id": "IB-LEAF-P0-L01",
            "plane_id": 0,
            "leaf_id": 1,
            "neighbors": [
                {"port_id": "p1", "neighbor_hostname": "B200-Rack01-Srv01-GPU1-HCA0"},
                {"port_id": "p2", "neighbor_hostname": "B200-Rack01-Srv02-GPU1-HCA0"}
            ]
        }
        
    Example Response (Mis-wire Detected):
        {
            "status": "COMPLETE",
            "cluster_healthy": false,
            "failed": 2,
            "swap_recommendations": ["🔄 Swap cables: Port 1 ↔ Port 2"]
        }
    """
    print(f"\n{'='*70}")
    print("🔍 CABLING VALIDATION REQUEST")
    print(f"   Switch: {body.switch_id}")
    print(f"   Plane: {body.plane_id}, Leaf: {body.leaf_id}")
    print(f"   Neighbors: {len(body.neighbors)}")
    print(f"{'='*70}")
    
    # Step 1: Fetch topology profile from Firestore
    firestore_client = get_firestore_client()
    project_id = get_project_id()
    
    # Query for this switch in extracted_devices to get topology
    query = (
        firestore_client
        .collection("extracted_devices")
        .where("projectId", "==", project_id)
        .where("deviceName", "==", body.switch_id)
        .limit(1)
        .stream()
    )
    
    device_doc = None
    for doc in query:
        device_doc = doc.to_dict()
        break
    
    if not device_doc:
        print(f"❌ Switch {body.switch_id} not found in inventory")
        raise HTTPException(
            status_code=404,
            detail=f"Switch {body.switch_id} not found in inventory"
        )
    
    # Extract topology profile
    topology_dict = device_doc.get("topologyProfile")
    if not topology_dict:
        print("❌ No topology profile found for switch")
        raise HTTPException(
            status_code=400,
            detail="Switch does not have topology profile configured"
        )
    
    # Step 2: Initialize validator with topology
    try:
        from app.libs.topology_profile import TopologyProfile
        from app.libs.wiring_validator import (
            WiringValidator,
            LLDPNeighborInfo as ValidatorNeighbor
        )
        
        topology_profile = TopologyProfile.from_dict(topology_dict)
        topology = topology_profile.to_cluster_topology()
        
        from app.libs.gpu_to_leaf_mapper import GPUToLeafMapper
        mapper = GPUToLeafMapper(topology)
        
        validator = WiringValidator(topology, mapper)
        
    except Exception as e:
        print(f"❌ Failed to initialize validator: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize topology validator: {str(e)}"
        )
    
    # Step 3: Convert Pydantic neighbors to validator format
    validator_neighbors = [
        ValidatorNeighbor(
            port_id=n.port_id,
            neighbor_hostname=n.neighbor_hostname,
            neighbor_description=n.neighbor_description,
            neighbor_mac=n.neighbor_mac
        )
        for n in body.neighbors
    ]
    
    # Step 4: Run validation
    try:
        report = validator.validate_cabling(
            switch_id=body.switch_id,
            plane_id=body.plane_id,
            leaf_id=body.leaf_id,
            actual_neighbors=validator_neighbors
        )
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )
    
    # Step 4.5: Run rail isolation check (CRITICAL for 8-rail GPU clusters)
    rail_violations = []  # Initialize before try-except to avoid scope issues
    try:
        print(f"\n🚨 Running rail isolation check for Plane {body.plane_id}...")
        rail_violations = validator.validate_rail_isolation(
            switch_id=body.switch_id,
            plane_id=body.plane_id,
            actual_neighbors=validator_neighbors
        )
    except Exception as e:
        print(f"❌ Rail isolation check failed: {e}")
        rail_violations = []
    
    # Step 4.6: Run SU boundary enforcement (CRITICAL for multi-SU SuperPODs)
    su_violations = []  # Initialize before try-except to avoid scope issues
    try:
        print(f"\n🛡️ Running SU boundary enforcement for {body.switch_id}...")
        su_violations = validator.validate_su_boundary_enforcement(
            switch_id=body.switch_id,
            actual_neighbors=validator_neighbors
        )
        if su_violations:
            print(f"🚨 CRITICAL: Detected {len(su_violations)} cross-SU contamination(s)")
    except Exception as e:
        print(f"❌ SU boundary check failed: {e}")
        su_violations = []
    
    # Step 5: Create alerts for failures
    if not report.cluster_healthy:
        print(f"\n⚠️ Creating alerts for {report.failed} mis-wires")
        
        # Create alerts for port-level wiring errors
        for result in report.results:
            if result.status == "FAIL":
                # Create provisioning alert
                firestore_client.collection("provisioning_alerts").add({
                    "projectId": project_id,
                    "severity": "CRITICAL",
                    "type": "WIRING_MISMATCH",
                    "status": "UNRESOLVED",
                    "switchId": body.switch_id,
                    "portId": result.port_id,
                    "portNumber": result.port_number,
                    "expected": result.expected_neighbor,
                    "actual": result.actual_neighbor,
                    "message": f"Wiring mismatch on {body.switch_id} port {result.port_id}",
                    "impact": "Cross-connection detected. Will degrade All-Reduce performance.",
                    "recommendation": result.swap_recommendation or result.mismatch_details,
                    "mismatchDetails": result.mismatch_details,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "resolvedAt": None
                })
        
        # Create alerts for rail contamination (CRITICAL)
        if rail_violations:
            print(f"\n🚨 Creating CRITICAL alerts for {len(rail_violations)} rail violations")
            for violation in rail_violations:
                firestore_client.collection("provisioning_alerts").add({
                    "projectId": project_id,
                    "severity": "CRITICAL",
                    "type": violation['violation_type'],  # "RAIL_CONTAMINATION" or "UNKNOWN_TAIL"
                    "status": "UNRESOLVED",
                    "switchId": body.switch_id,
                    "portId": violation['port_id'],
                    "expectedPlane": violation['expected_plane'],
                    "actualTail": violation['actual_tail'],
                    "neighborHostname": violation['neighbor_hostname'],
                    "message": f"Rail contamination on {body.switch_id} port {violation['port_id']}",
                    "impact": violation['impact'],
                    "recommendation": violation['action'],
                    "violationType": violation['violation_type'],
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "resolvedAt": None
                })
    
    # Create alerts for SU boundary contamination (HIGHEST PRIORITY)
    if su_violations:
        print(f"\n🔴 Creating CRITICAL alerts for {len(su_violations)} SU boundary breaches")
        for violation in su_violations:
            firestore_client.collection("provisioning_alerts").add({
                "projectId": project_id,
                "severity": "CRITICAL",
                "type": violation['violation_type'],  # "CROSS_SU_CONTAMINATION" or "SU_PARSE_FAILURE"
                "status": "UNRESOLVED",
                "switchId": body.switch_id,
                "portId": violation['port_id'],
                "expectedSuId": violation['expected_su_id'],
                "actualSuId": violation['actual_su_id'],
                "neighborHostname": violation['neighbor_hostname'],
                "message": f"Cross-SU contamination on {body.switch_id} port {violation['port_id']}",
                "impact": violation['impact'],
                "recommendation": violation['action'],
                "violationType": violation['violation_type'],
                "createdAt": firestore.SERVER_TIMESTAMP,
                "resolvedAt": None
            })
    
    # Step 6: Update switch status in Firestore
    status_update = "OPERATIONAL" if report.cluster_healthy else "WIRING_ERROR"
    
    # Update live_infrastructure collection
    switch_query = (
        firestore_client
        .collection("live_infrastructure")
        .where("projectId", "==", project_id)
        .where("deviceName", "==", body.switch_id)
        .limit(1)
        .stream()
    )
    
    for doc in switch_query:
        doc.reference.update({
            "status": status_update,
            "cablingValidated": True,
            "cablingHealthy": report.cluster_healthy,
            "cablingHealthPercentage": report.health_percentage,
            "cablingValidatedAt": firestore.SERVER_TIMESTAMP,
            "cablingPassedPorts": report.passed,
            "cablingFailedPorts": report.failed,
            "cablingMissingPorts": report.missing
        })
        print(f"✅ Updated switch status: {status_update}")
        break
    
    # Step 7: Convert report to response format
    response_results = [
        PortValidationResultModel(
            port_id=r.port_id,
            port_number=r.port_number,
            status=r.status,
            expected_neighbor=r.expected_neighbor,
            actual_neighbor=r.actual_neighbor,
            mismatch_details=r.mismatch_details,
            swap_recommendation=r.swap_recommendation
        )
        for r in report.results
    ]
    
    print(f"\n✅ Validation complete: {report.health_percentage:.1f}% healthy")
    
    # Convert rail violations to Pydantic models
    rail_violation_models = [
        RailViolationModel(
            port_id=v['port_id'],
            expected_plane=v['expected_plane'],
            actual_tail=v.get('actual_tail'),
            neighbor_hostname=v['neighbor_hostname'],
            severity=v['severity'],
            violation_type=v['violation_type'],
            impact=v['impact'],
            action=v['action']
        )
        for v in rail_violations
    ]
    
    # Convert SU violations to Pydantic models
    su_violation_models = [
        SUBoundaryViolationModel(
            port_id=v['port_id'],
            neighbor_hostname=v['neighbor_hostname'],
            expected_su_id=v['expected_su_id'],
            actual_su_id=v['actual_su_id'],
            severity=v['severity'],
            violation_type=v['violation_type'],
            impact=v['impact'],
            action=v['action']
        )
        for v in su_violations
    ]
    
    return CablingValidationResponse(
        status="COMPLETE",
        switch_id=report.switch_id,
        plane_id=report.plane_id,
        leaf_id=report.leaf_id,
        cluster_healthy=report.cluster_healthy,
        total_ports=report.total_ports,
        passed=report.passed,
        failed=report.failed,
        missing=report.missing,
        health_percentage=report.health_percentage,
        results=response_results,
        swap_recommendations=report.swap_recommendations,
        rail_violations=rail_violation_models,
        has_rail_contamination=len(rail_violations) > 0,
        su_violations=su_violation_models,
        has_su_contamination=len(su_violations) > 0
    )
