from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel
import databutton as db  # type: ignore
import os
from datetime import datetime
import uuid
from typing import Optional, Literal
from app.libs.firestore_scoping import get_scoped_collection
from app.libs.firebase_config import get_firestore_client

router = APIRouter(prefix="/cluster-bringup")

# Helper function to get customer_id (will be replaced with middleware)
def get_customer_id() -> str:
    """Get customer_id from auth context.
    
    TODO: Replace with proper customer extraction from auth middleware.
    For now, returns default customer for backward compatibility.
    """
    return "default"

# ============== MODELS ==============

class ColorLegendEntry(BaseModel):
    color: str
    connectionType: str
    bandwidth: str

class DeviceConventions(BaseModel):
    computePrefix: str
    storagePrefix: str
    switchLeafPrefix: str
    switchSpinePrefix: str

class ProcessingConfig(BaseModel):
    autoExpandTrunks: bool
    validateRailAlignment: bool
    spotCheckSampleSize: int

class SchematicConfigRequest(BaseModel):
    project_id: str
    color_legend: list[ColorLegendEntry]
    device_conventions: DeviceConventions
    processing_config: ProcessingConfig

class SchematicUploadResponse(BaseModel):
    project_id: str
    schematic_url: str
    status: str

class ProcessingStatusResponse(BaseModel):
    project_id: str
    status: str
    progress_percentage: int
    current_stage: str
    error_message: Optional[str]

class ProjectListResponse(BaseModel):
    """Response model for listing cluster bringup projects"""
    projects: list[dict]

class AssetInventoryUploadResponse(BaseModel):
    """Response model for asset inventory upload"""
    success: bool
    matchedCount: int
    unmatchedSchematicDevices: list[str]
    unmatchedInventoryDevices: list[dict]
    validationReport: str

class MergeValidationResponse(BaseModel):
    """Response model for merge validation"""
    project_id: str
    total_devices: int
    verified_count: int
    pending_count: int
    devices: list[dict]

# Network Tier Classification
NetworkTier = Literal["BACKEND_FABRIC", "FRONTEND_FABRIC", "OOB_MANAGEMENT", "UNKNOWN"]

class NetworkMetadata(BaseModel):
    """Network-specific metadata for switches and network devices"""
    tier: NetworkTier
    protocol: Optional[str] = None  # InfiniBand, Ethernet, etc.
    link_speed_capability: Optional[str] = None  # 400G, 100G, 1G
    fabric_type: Optional[str] = None  # Compute_Fabric, Storage_Fabric, OOB_Mgmt
    port_count_detected: Optional[int] = None
    connector_type: Optional[str] = None  # OSFP, QSFP, RJ45
    switch_role: Optional[str] = None  # leaf, spine, core, management
    confidence_score: Optional[float] = None
    evidence: Optional[str] = None  # Why the AI classified it this way

class HardwareInfo(BaseModel):
    """Hardware details from asset inventory CSV"""
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    form_factor: Optional[str] = None
    serial_number: Optional[str] = None
    asset_tag: Optional[str] = None
    mac_address: Optional[str] = None
    purchase_date: Optional[str] = None
    warranty_expiry: Optional[str] = None

class LocationInfo(BaseModel):
    """5-level hierarchical location (DCIM standard)"""
    site: Optional[str] = None
    room: Optional[str] = None
    row: Optional[str] = None
    rack: Optional[str] = None
    u_position: Optional[str] = None

class Device(BaseModel):
    deviceId: str
    deviceName: str
    deviceType: Optional[str] = "other"  # compute, storage, network
    rackLocation: Optional[str] = "Unknown"  # Deprecated, use LocationInfo
    position: Optional[dict] = None
    ports: Optional[list[dict]] = None
    metadata: Optional[dict] = None
    # Enhanced fields
    location: Optional[LocationInfo] = None
    hardware_info: Optional[HardwareInfo] = None
    network_metadata: Optional[NetworkMetadata] = None
    verification_status: Optional[str] = "pending"  # pending, verified, mismatch

class PortInfo(BaseModel):
    """Enhanced port information"""
    port_label: str
    port_type: Optional[str] = None  # OSFP, QSFP, RJ45, etc.

class Connection(BaseModel):
    connectionId: str
    sourceDevice: Optional[str] = None
    sourcePort: Optional[str] = None
    destinationDevice: Optional[str] = None
    destinationPort: Optional[str] = None
    connectionType: Optional[str] = "Unknown"
    bandwidth: Optional[str] = "Unknown"
    isTrunk: Optional[bool] = False
    trunkSize: Optional[int] = None
    # Enhanced fields
    segment: Optional[NetworkTier] = "UNKNOWN"
    network_purpose: Optional[str] = None  # gpu-fabric, tenant-access, management, storage-io
    source_port_info: Optional[PortInfo] = None
    dest_port_info: Optional[PortInfo] = None
    validation_status: Optional[str] = "compliant"  # compliant, role_mismatch, port_mismatch

class ExtractionResultsResponse(BaseModel):
    devices: list[Device]
    connections: list[Connection]

# NEW: Tier Health Models
class TierHealthResponse(BaseModel):
    health: str
    total_devices: int
    operational_devices: int
    percentage: float
    blocking_reason: Optional[str] = None

class ClusterReadinessResponse(BaseModel):
    timestamp: str
    tiers: dict

class EmergencyOverrideRequest(BaseModel):
    device_name: str
    override_token: str
    reason: str

# NEW: IP Allocation Models
class IPAllocationPreviewResponse(BaseModel):
    total_ips: int
    ip_allocations: list[dict]
    conflicts: list[dict]
    status: str
    summary: dict

# ============== ENDPOINTS ==============

@router.post("/upload-schematic")
async def upload_schematic_file(
    schematic_file: UploadFile = File(...),
) -> SchematicUploadResponse:
    """Upload a data center schematic for processing"""
    
    # Generate project ID
    project_id = f"bringup_{uuid.uuid4().hex[:12]}"
    
    # Read and store file
    file_content = await schematic_file.read()
    file_extension = schematic_file.filename.split('.')[-1] if schematic_file.filename else 'bin'
    storage_key = f"cluster_bringup/{project_id}/schematic.{file_extension}"
    
    from app.libs.firebase_config import get_storage_bucket
    bucket = get_storage_bucket()
    blob = bucket.blob(storage_key)
    blob.upload_from_string(file_content, content_type=schematic_file.content_type)    
    # Create project record in Firestore
    from google.cloud import firestore  # type: ignore
    firestore_client = get_firestore_client()
    customer_id = get_customer_id()
    
    project_name = f"Cluster Bringup {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    project_doc = {
        "projectId": project_id,
        "projectName": project_name,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "status": "uploaded",
        "schematicUrl": storage_key,
        "schematicFilename": schematic_file.filename or "schematic",
        "colorLegend": {},
        "deviceConventions": {},
        "processingConfig": {},
    }
    
    get_scoped_collection(firestore_client, customer_id, "cluster_bringup_projects").document(project_id).set(project_doc)
    
    return SchematicUploadResponse(
        project_id=project_id,
        schematic_url=storage_key,
        status="uploaded"
    )


@router.post("/configure-processing")
async def configure_schematic_processing(body: SchematicConfigRequest, background_tasks: BackgroundTasks):
    """Configure color legend and processing options"""
    
    from app.libs.firebase_config import get_firestore_client
    from google.cloud import firestore  # type: ignore
    firestore_client = get_firestore_client()
    customer_id = get_customer_id()
    
    # Update project with configuration
    project_ref = get_scoped_collection(firestore_client, customer_id, "cluster_bringup_projects").document(body.project_id)
    
    # Check if project exists
    if not project_ref.get().exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_ref.update({
        "colorLegend": {entry.color: {"connectionType": entry.connectionType, "bandwidth": entry.bandwidth} 
                       for entry in body.color_legend},
        "deviceConventions": body.device_conventions.dict(),
        "processingConfig": body.processing_config.dict(),
        "status": "configured"
    })
    
    # Trigger AI processing in background
    from app.libs.schematic_processor import trigger_schematic_processing
    
    try:
        # Offload heavyweight vision AI extraction to background thread
        background_tasks.add_task(trigger_schematic_processing, body.project_id, customer_id)
    except Exception as e:
        print(f"Processing error: {str(e)}")
        # Don't fail the request - error is already logged in Firestore
    
    return {"status": "processing_started", "project_id": body.project_id}


@router.get("/processing-status/{project_id}")
async def get_processing_status(project_id: str) -> ProcessingStatusResponse:
    """Get current processing status"""
    
    from google.cloud import firestore  # type: ignore
    firestore_client = get_firestore_client()
    customer_id = get_customer_id()
    
    project_doc = get_scoped_collection(firestore_client, customer_id, "cluster_bringup_projects").document(project_id).get()
    
    if not project_doc.exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    data = project_doc.to_dict()
    
    return ProcessingStatusResponse(
        project_id=project_id,
        status=data.get("status", "unknown"),
        progress_percentage=data.get("progressPercentage", 0),
        current_stage=data.get("currentStage", ""),
        error_message=data.get("errorMessage")
    )


@router.get("/extraction-results/{project_id}")
async def get_extraction_results(project_id: str) -> ExtractionResultsResponse:
    """Get extracted devices and connections"""
    
    from google.cloud import firestore  # type: ignore
    firestore_client = get_firestore_client()
    customer_id = get_customer_id()
    
    # Fetch devices
    devices_query = get_scoped_collection(firestore_client, customer_id, "extracted_devices").where("projectId", "==", project_id).stream()
    devices = [Device(**doc.to_dict()) for doc in devices_query]
    
    # Fetch connections
    connections_query = get_scoped_collection(firestore_client, customer_id, "extracted_connections").where("projectId", "==", project_id).stream()
    connections = [Connection(**doc.to_dict()) for doc in connections_query]
    
    # Fetch validation report
    validation_docs = get_scoped_collection(firestore_client, customer_id, "validation_reports").where("projectId", "==", project_id).limit(1).stream()
    validation_summary = {}
    for doc in validation_docs:
        validation_summary = doc.to_dict()
        break
    
    return ExtractionResultsResponse(
        devices=devices,
        connections=connections,
        validation_summary=validation_summary
    )


@router.get("/export-cabling-matrix/{project_id}")
async def export_cabling_matrix(project_id: str):
    """Export cabling matrix as CSV"""
    
    from app.libs.matrix_exporter import generate_cabling_matrix_csv
    
    customer_id = get_customer_id()
    
    try:
        csv_content = generate_cabling_matrix_csv(project_id, customer_id)
        
        # Return as downloadable CSV file
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=cabling_matrix_{project_id}.csv"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/projects")
async def list_projects() -> ProjectListResponse:
    """List all cluster bringup projects"""
    
    from google.cloud import firestore  # type: ignore
    firestore_client = get_firestore_client()
    customer_id = get_customer_id()
    
    projects_query = get_scoped_collection(firestore_client, customer_id, "cluster_bringup_projects").order_by("createdAt", direction=firestore.Query.DESCENDING).limit(50).stream()
    
    projects = []
    for doc in projects_query:
        project_data = doc.to_dict()
        projects.append({
            "projectId": project_data.get("projectId"),
            "projectName": project_data.get("projectName"),
            "status": project_data.get("status"),
            "createdAt": project_data.get("createdAt"),
            "schematicFilename": project_data.get("schematicFilename")
        })
    
    return ProjectListResponse(projects=projects)


@router.delete("/project/{project_id}")
async def delete_project(project_id: str):
    """Delete a cluster bringup project and all associated data"""
    
    from google.cloud import firestore  # type: ignore
    firestore_client = get_firestore_client()
    customer_id = get_customer_id()
    
    # Delete project document
    project_ref = get_scoped_collection(firestore_client, customer_id, "cluster_bringup_projects").document(project_id)
    if not project_ref.get().exists:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_ref.delete()
    
    # Delete devices
    devices_query = get_scoped_collection(firestore_client, customer_id, "extracted_devices").where("projectId", "==", project_id).stream()
    for doc in devices_query:
        doc.reference.delete()
    
    # Delete connections
    connections_query = get_scoped_collection(firestore_client, customer_id, "extracted_connections").where("projectId", "==", project_id).stream()
    for doc in connections_query:
        doc.reference.delete()
    
    # Delete validation reports
    reports_query = get_scoped_collection(firestore_client, customer_id, "validation_reports").where("projectId", "==", project_id).stream()
    for doc in reports_query:
        doc.reference.delete()
    
    return {"status": "deleted", "project_id": project_id}


@router.post("/upload-asset-inventory/{project_id}")
async def upload_asset_inventory(
    project_id: str,
    file: UploadFile = File(...)
) -> AssetInventoryUploadResponse:
    """
    Upload asset inventory CSV and merge with extracted devices based on location hierarchy.
    
    Expected CSV columns:
    - Site, Room, Row, Rack, U-Position (or UPosition)
    - Serial Number (or SerialNumber)
    - Asset Tag (or AssetTag)
    - Manufacturer
    - Model
    - MAC Address (optional)
    - Purchase Date (optional)
    - Warranty Expiry (optional)
    """
    import csv
    import io
    from google.cloud import firestore  # type: ignore
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")
    
    try:
        # Read CSV content
        contents = await file.read()
        csv_text = contents.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        # Normalize column names (handle spaces, case variations)
        def normalize_key(key: str) -> str:
            return key.strip().lower().replace(' ', '_').replace('-', '_')
        
        inventory_items = []
        for row in csv_reader:
            normalized_row = {normalize_key(k): v.strip() for k, v in row.items() if v and v.strip()}
            if normalized_row:  # Only add non-empty rows
                inventory_items.append(normalized_row)
        
        print(f"📦 Loaded {len(inventory_items)} items from asset inventory CSV")
        
        # Fetch extracted devices from Firestore
        firestore_client = get_firestore_client()
        customer_id = get_customer_id()
        devices_query = get_scoped_collection(firestore_client, customer_id, "extracted_devices").where("projectId", "==", project_id).stream()
        devices = {doc.id: doc.to_dict() for doc in devices_query}
        
        print(f"🖥️ Found {len(devices)} devices from schematic extraction")
        
        # Match inventory to devices based on location hierarchy
        matched_count = 0
        unmatched_schematic = []
        unmatched_inventory = []
        
        batch = firestore_client.batch()
        
        for device_id, device_data in devices.items():
            # Build location key for matching
            device_location = {
                'site': (device_data.get('site') or '').lower().strip(),
                'room': (device_data.get('room') or '').lower().strip(),
                'row': (device_data.get('row') or '').lower().strip(),
                'rack': (device_data.get('rack') or '').lower().strip(),
                'u_position': (device_data.get('uPosition') or '').lower().strip(),
            }
            
            # Find matching inventory item
            match_found = False
            for inv_item in inventory_items:
                inv_location = {
                    'site': inv_item.get('site', '').lower().strip(),
                    'room': inv_item.get('room', '').lower().strip(),
                    'row': inv_item.get('row', '').lower().strip(),
                    'rack': inv_item.get('rack', '').lower().strip(),
                    'u_position': inv_item.get('u_position', inv_item.get('uposition', '')).lower().strip(),
                }
                
                # STRICT MATCHING: All 5 levels must match exactly
                # If any level is missing from either source, it's not a match
                # This ensures DCIM-grade precision for compliance and warranty tracking
                
                all_levels_present_device = all([
                    device_location['site'],
                    device_location['room'], 
                    device_location['row'],
                    device_location['rack'],
                    device_location['u_position']
                ])
                
                all_levels_present_inventory = all([
                    inv_location['site'],
                    inv_location['room'],
                    inv_location['row'],
                    inv_location['rack'],
                    inv_location['u_position']
                ])
                
                # Both must have complete location hierarchy
                if not (all_levels_present_device and all_levels_present_inventory):
                    continue
                
                # Exact match on all 5 levels
                if (device_location['site'] == inv_location['site'] and
                    device_location['room'] == inv_location['room'] and
                    device_location['row'] == inv_location['row'] and
                    device_location['rack'] == inv_location['rack'] and
                    device_location['u_position'] == inv_location['u_position']):
                    
                    # Match found! Merge hardware details
                    doc_ref = get_scoped_collection(firestore_client, customer_id, "extracted_devices").document(device_id)
                    batch.update(doc_ref, {
                        "serialNumber": inv_item.get('serial_number', inv_item.get('serialnumber')),
                        "assetTag": inv_item.get('asset_tag', inv_item.get('assettag')),
                        "manufacturer": inv_item.get('manufacturer'),
                        "model": inv_item.get('model'),
                        "macAddress": inv_item.get('mac_address', inv_item.get('macaddress')),
                        "purchaseDate": inv_item.get('purchase_date', inv_item.get('purchasedate')),
                        "warrantyExpiry": inv_item.get('warranty_expiry', inv_item.get('warrantyexpiry')),
                        "verificationStatus": "verified",
                        "mergedAt": firestore.SERVER_TIMESTAMP
                    })
                    
                    matched_count += 1
                    match_found = True
                    inventory_items.remove(inv_item)  # Remove from unmatched list
                    break
            
            if not match_found:
                device_name = device_data.get('deviceName', 'Unknown')
                device_loc = f"{device_data.get('site', 'N/A')}/{device_data.get('room', 'N/A')}/{device_data.get('row', 'N/A')}/{device_data.get('rack', 'N/A')}/{device_data.get('uPosition', 'N/A')}"
                unmatched_schematic.append(f"{device_name} ({device_loc})")
        
        # Commit batch updates
        batch.commit()
        
        # Remaining inventory items are unmatched
        unmatched_inventory = [
            {
                "rack": item.get('rack', 'Unknown'),
                "uPosition": item.get('u_position', item.get('uposition', 'Unknown')),
                "serialNumber": item.get('serial_number', item.get('serialnumber', 'No SN')),
                "manufacturer": item.get('manufacturer', 'Unknown')
            }
            for item in inventory_items
        ]
        
        # Generate validation report
        validation_report = f"""=== ASSET INVENTORY MERGE REPORT ===

Matched Devices: {matched_count}
Unmatched Schematic Devices: {len(unmatched_schematic)}
Unmatched Inventory Items: {len(unmatched_inventory)}

--- Unmatched Schematic Devices ---
{chr(10).join(f"- {dev}" for dev in unmatched_schematic) if unmatched_schematic else "None"}

--- Unmatched Inventory Items (not found in schematic) ---
{chr(10).join(f"- {item['rack']}/{item['uPosition']}: {item['serialNumber']} ({item['manufacturer']})" for item in unmatched_inventory) if unmatched_inventory else "None"}
"""
        
        print(validation_report)
        
        return AssetInventoryUploadResponse(
            success=True,
            matchedCount=matched_count,
            unmatchedSchematicDevices=unmatched_schematic,
            unmatchedInventoryDevices=unmatched_inventory,
            validationReport=validation_report
        )
        
    except Exception as e:
        print(f"❌ Asset inventory upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process asset inventory: {str(e)}")


@router.get("/merge-validation/{project_id}")
def get_merge_validation(project_id: str) -> MergeValidationResponse:
    """
    Get validation report showing which devices have been verified against asset inventory.
    """
    from google.cloud import firestore  # type: ignore
    
    try:
        firestore_client = get_firestore_client()
        customer_id = get_customer_id()
        devices_query = get_scoped_collection(firestore_client, customer_id, "extracted_devices").where("projectId", "==", project_id).stream()
        
        devices = []
        verified_count = 0
        pending_count = 0
        mismatch_count = 0
        
        for doc in devices_query:
            device_data = doc.to_dict()
            status = device_data.get('verificationStatus', 'pending')
            
            if status == 'verified':
                verified_count += 1
            elif status == 'mismatch':
                mismatch_count += 1
            else:
                pending_count += 1
            
            devices.append({
                "deviceName": device_data.get('deviceName'),
                "location": f"{device_data.get('site', '')}/{device_data.get('room', '')}/{device_data.get('row', '')}/{device_data.get('rack', 'Unknown')}/{device_data.get('uPosition', 'Unknown')}",
                "serialNumber": device_data.get('serialNumber'),
                "assetTag": device_data.get('assetTag'),
                "manufacturer": device_data.get('manufacturer'),
                "model": device_data.get('model'),
                "verificationStatus": status
            })
        
        return MergeValidationResponse(
            projectId=project_id,
            totalDevices=len(devices),
            verifiedCount=verified_count,
            pendingCount=pending_count,
            mismatchCount=mismatch_count,
            devices=devices
        )
        
    except Exception as e:
        print(f"❌ Failed to get merge validation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get validation report: {str(e)}")


@router.get("/download-asset-template")
def download_asset_template():
    """
    Download a sample CSV template for asset inventory with network-specific columns.
    Provides proper column headers and example data for procurement teams.
    """
    import csv
    import io
    
    # Create CSV with example data
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row with network-specific columns
    writer.writerow([
        "Site",
        "Room",
        "Row",
        "Rack",
        "U-Position",
        "Serial Number",
        "Asset Tag",
        "Manufacturer",
        "Model",
        "MAC Address",
        "Purchase Date",
        "Warranty Expiry",
        # Network-specific columns
        "Device Role",
        "Network Segment",
        "Total Ports",
        "Uplink Port Range",
        "Downlink Port Range",
        "Connector Type",
        "Cable Type",  # NEW: Cable breakout configuration
        "Firmware Version",
        "Management IP",
        "Rail ID"
    ])
    
    # Example 1: DGX H100 GPU Compute Node
    writer.writerow([
        "DC-Austin",
        "Hall-A",
        "Row-1",
        "Rack-01",
        "U10",
        "SN12345DGX01",
        "TAG-GPU-001",
        "NVIDIA",
        "DGX H100",
        "AA:BB:CC:DD:EE:01",
        "2024-01-15",
        "2027-01-15",
        "GPU_Compute",
        "BACKEND_FABRIC",
        "8",
        "",
        "",
        "OSFP",
        "",
        "10.1.1.10",
        "Rail-0"
    ])
    
    # Example 2: Storage Node
    writer.writerow([
        "DC-Austin",
        "Hall-A",
        "Row-1",
        "Rack-02",
        "U20",
        "SN67890STOR01",
        "TAG-STOR-001",
        "Dell",
        "PowerEdge R750",
        "AA:BB:CC:DD:EE:02",
        "2024-01-15",
        "2027-01-15",
        "Storage_Server",
        "FRONTEND_FABRIC",
        "4",
        "",
        "",
        "QSFP",
        "",
        "10.1.1.20",
        ""
    ])
    
    # Example 3: InfiniBand Spine Switch (Backend Fabric)
    writer.writerow([
        "DC-Austin",
        "Hall-A",
        "Row-1",
        "Rack-03",
        "U42",
        "SNIB-SPINE-01",
        "TAG-IB-SPINE-01",
        "NVIDIA",
        "Quantum-2 QM9700",
        "",
        "2024-02-01",
        "2027-02-01",
        "IB_Spine",
        "BACKEND_FABRIC",
        "64",
        "49-64",
        "1-48",
        "OSFP",
        "3.9.2100",
        "10.1.254.1",
        "Rail-0"
    ])
    
    # Example 4: InfiniBand Leaf Switch (Backend Fabric)
    writer.writerow([
        "DC-Austin",
        "Hall-A",
        "Row-1",
        "Rack-03",
        "U38",
        "SNIB-LEAF-01",
        "TAG-IB-LEAF-01",
        "NVIDIA",
        "Quantum-2 QM9700",
        "",
        "2024-02-01",
        "2027-02-01",
        "IB_Leaf",
        "BACKEND_FABRIC",
        "64",
        "49-64",
        "1-48",
        "OSFP",
        "3.9.2100",
        "10.1.254.2",
        "Rail-0"
    ])
    
    # Example 5: Frontend Ethernet Switch
    writer.writerow([
        "DC-Austin",
        "Hall-A",
        "Row-1",
        "Rack-04",
        "U42",
        "SNFE-SW-01",
        "TAG-FE-SW-01",
        "Arista",
        "7280SR3-48YC8",
        "",
        "2024-02-01",
        "2027-02-01",
        "FE_Switch",
        "FRONTEND_FABRIC",
        "48",
        "41-48",
        "1-40",
        "QSFP",
        "4.28.3M",
        "10.1.254.10",
        ""
    ])
    
    # Example 6: OOB Management Switch
    writer.writerow([
        "DC-Austin",
        "Hall-A",
        "Row-1",
        "Rack-04",
        "U44",
        "SNOOB-MGT-01",
        "TAG-OOB-01",
        "Cisco",
        "Catalyst 9300-48P",
        "",
        "2024-02-01",
        "2027-02-01",
        "OOB_Switch",
        "OOB_MANAGEMENT",
        "48",
        "45-48",
        "1-44",
        "RJ45",
        "17.9.1",
        "10.1.254.100",
        ""
    ])
    
    # Return CSV as downloadable file
    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=asset_inventory_template.csv"}
    )


@router.get("/download-test-schematic")
def download_test_schematic():
    """
    Download the test 3-tier network schematic PNG for testing the cluster bringup workflow.
    Includes BACKEND_FABRIC, FRONTEND_FABRIC, and OOB_MANAGEMENT tiers with intentional validation issues.
    """
    import databutton as db
    
    try:
        schematic_bytes = db.storage.binary.get("test_3tier_network_schematic.png")
        
        return Response(
            content=schematic_bytes,
            media_type="image/png",
            headers={"Content-Disposition": "attachment; filename=test_3tier_network_schematic.png"}
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Test schematic not found. Run the test data generation script first.")


@router.get("/download-test-csv")
def download_test_csv():
    """
    Download the test 3-tier asset inventory CSV for testing the cluster bringup workflow.
    Includes network segment, device role, and port information for validation testing.
    """
    import databutton as db
    
    try:
        csv_content = db.storage.text.get("test_3tier_asset_inventory.csv")
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=test_3tier_asset_inventory.csv"}
        )
    except Exception:
        raise HTTPException(status_code=404, detail="Test CSV not found. Run the test data generation script first.")


# ============== DAY 1 PROVISIONING ENDPOINTS ==============

class DHCPDiscoverRequest(BaseModel):
    """DHCP DISCOVER webhook payload from DHCP server"""
    mac: str
    remote_id: Optional[str] = None  # DHCP Option 82 data (switch port info)
    relay_agent_ip: Optional[str] = None
    hostname: Optional[str] = None

class DHCPDiscoverResponse(BaseModel):
    """Response to DHCP server indicating whether to assign IP"""
    status: str  # "SUCCESS", "BLOCKED", "UNKNOWN", "UNREACHABLE"
    device_name: Optional[str] = None
    assigned_ip: Optional[str] = None
    location: Optional[str] = None
    alert_id: Optional[str] = None
    reason: Optional[str] = None
    expected_serial: Optional[str] = None
    detected_serial: Optional[str] = None

class ProvisioningAlert(BaseModel):
    """Alert for Installation Lead dashboard"""
    alert_id: str
    project_id: str
    severity: str  # "CRITICAL", "HIGH", "MEDIUM"
    type: str  # "IDENTITY_MISMATCH", "UNKNOWN_DEVICE", "UNREACHABLE_SWITCH"
    status: str  # "UNRESOLVED", "RESOLVED"
    location: Optional[dict] = None
    planned: Optional[dict] = None
    detected: Optional[dict] = None
    message: str
    impact: str
    recommendation: str
    created_at: str
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_action: Optional[str] = None

class ResolveAlertRequest(BaseModel):
    """Installation Lead's resolution action"""
    alert_id: str
    strategy: str  # "SWAP_HARDWARE", "UPDATE_INVENTORY", "OVERRIDE_AND_PROCEED"
    resolved_by: str  # User ID or email

class ResolveAlertResponse(BaseModel):
    status: str
    message: str


@router.post("/provisioning/discover/{project_id}")
async def dhcp_discovery_webhook(
    project_id: str,
    body: DHCPDiscoverRequest
) -> DHCPDiscoverResponse:
    """
    **DHCP Server Webhook Endpoint**
    
    Called by the DHCP server (ISC Kea, Infoblox, etc.) when a new device
    sends a DHCP DISCOVER packet during initial power-on.
    
    This is the "gatekeeper" that prevents wrong hardware from getting IPs.
    
    **Flow:**
    1. DHCP server detects new MAC address
    2. Calls this webhook with MAC and optional metadata
    3. DHCPScraper verifies hardware identity
    4. Returns SUCCESS (with IP) or BLOCKED (no IP assigned)
    
    **Security:**
    - If identity mismatch: Return HTTP 403 Forbidden
    - DHCP server should NOT assign IP on 403 response
    - Creates CRITICAL alert for Installation Lead
    
    **Integration Example (ISC Kea):**
    ```json
    {
        "hooks-libraries": [{
            "library": "/usr/lib/kea/hooks/libdhcp_lease_cmds.so",
            "parameters": {
                "on-discover-webhook": "https://yourdomain.riff.works/routes/cluster-bringup/provisioning/discover/PROJECT_ID"
            }
        }]
    }
    ```
    """
    from app.libs.dhcp_scraper import DHCPScraper
    
    print(f"\n{'='*70}")
    print("🔔 DHCP DISCOVERY WEBHOOK TRIGGERED")
    print(f"   Project: {project_id}")
    print(f"   MAC: {body.mac}")
    print(f"   Remote ID: {body.remote_id}")
    print(f"{'='*70}")
    
    try:
        # TODO: Extract customer_id from auth context or webhook URL
        # For now, use default customer for backward compatibility
        customer_id = "default"
        
        # Initialize scraper
        scraper = DHCPScraper(project_id=project_id, customer_id=customer_id)
        
        # Process discovery
        result = scraper.process_dhcp_discover(mac_address=body.mac)
        
        # Return response based on scraper result
        response = DHCPDiscoverResponse(
            status=result["status"],
            device_name=result.get("device_name"),
            assigned_ip=result.get("assigned_ip"),
            location=result.get("location"),
            alert_id=result.get("alert_id"),
            reason=result.get("reason"),
            expected_serial=result.get("expected_serial"),
            detected_serial=result.get("detected_serial")
        )
        
        # If BLOCKED, return 403 to prevent DHCP server from assigning IP
        if result["status"] == "BLOCKED":
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "IDENTITY_MISMATCH",
                    "message": "Hardware identity mismatch detected. IP assignment blocked.",
                    "alert_id": result.get("alert_id"),
                    "expected_serial": result.get("expected_serial"),
                    "detected_serial": result.get("detected_serial")
                }
            )
        
        return response
        
    except Exception as e:
        print(f"❌ Error processing DHCP discovery: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provisioning/alerts/{project_id}")
async def get_provisioning_alerts(project_id: str) -> list[ProvisioningAlert]:
    """
    **Get Active Provisioning Alerts**
    
    Returns all unresolved alerts for the Installation Lead dashboard.
    Ordered by severity (CRITICAL first) and creation time.
    
    **Use Case:**
    Frontend dashboard polls this endpoint every 5 seconds to show
    real-time alerts when hardware mismatches are detected.
    
    **Alert Types:**
    - IDENTITY_MISMATCH (CRITICAL): Wrong switch at location
    - UNKNOWN_DEVICE (MEDIUM): MAC not in Day 0 plan
    - UNREACHABLE_SWITCH (HIGH): Switch booted but no serial response
    """
    from google.cloud import firestore  # type: ignore
    
    firestore_client = get_firestore_client()
    
    # Query unresolved alerts for this project, ordered by severity
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    
    alerts_query = (
        firestore_client
        .collection("provisioning_alerts")
        .where("projectId", "==", project_id)
        .where("status", "==", "UNRESOLVED")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .stream()
    )
    
    alerts = []
    for doc in alerts_query:
        alert_data = doc.to_dict()
        
        # Convert Firestore timestamp to ISO string
        created_at = alert_data.get("createdAt")
        if created_at:
            created_at = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
        
        resolved_at = alert_data.get("resolvedAt")
        if resolved_at:
            resolved_at = resolved_at.isoformat() if hasattr(resolved_at, "isoformat") else str(resolved_at)
        
        alerts.append(ProvisioningAlert(
            alert_id=doc.id,
            project_id=alert_data.get("projectId"),
            severity=alert_data.get("severity"),
            type=alert_data.get("type"),
            status=alert_data.get("status"),
            location=alert_data.get("location"),
            planned=alert_data.get("planned"),
            detected=alert_data.get("detected"),
            message=alert_data.get("message"),
            impact=alert_data.get("impact"),
            recommendation=alert_data.get("recommendation"),
            created_at=created_at or "",
            resolved_at=resolved_at,
            resolved_by=alert_data.get("resolvedBy"),
            resolution_action=alert_data.get("resolutionAction")
        ))
    
    # Sort by severity (CRITICAL first, then HIGH, then MEDIUM)
    alerts.sort(key=lambda a: severity_order.get(a.severity, 999))
    
    print(f"🚨 Retrieved {len(alerts)} unresolved alerts for project {project_id}")
    
    return alerts


@router.post("/provisioning/resolve")
async def resolve_provisioning_alert(body: ResolveAlertRequest) -> ResolveAlertResponse:
    """
    **Installation Lead Resolves Alert**
    
    Three resolution strategies:
    
    1. **SWAP_HARDWARE**: Technician will physically move the switch.
       - Use when hardware was racked in wrong location
       - Marks alert as resolved, waits for physical correction
    
    2. **UPDATE_INVENTORY**: Accept detected hardware as correct.
       - Use when Day 0 inventory was wrong, physical reality is correct
       - Updates Firestore with actual serial, unblocks device
    
    3. **OVERRIDE_AND_PROCEED**: Proceed despite mismatch (DANGEROUS).
       - Use only when Installation Lead accepts the risk
       - ⚠️ Can lead to catastrophic configuration errors
       - Creates audit trail of override
    
    **Audit Trail:**
    All resolutions are logged with:
    - Who resolved it (user ID/email)
    - When it was resolved (timestamp)
    - Which strategy was used
    - Resolution outcome
    """
    from app.libs.dhcp_scraper import resolve_identity_mismatch
    
    print(f"\n👨‍🔧 Installation Lead resolving alert {body.alert_id}")
    print(f"   Strategy: {body.strategy}")
    print(f"   Resolved by: {body.resolved_by}")
    
    try:
        result = resolve_identity_mismatch(
            alert_id=body.alert_id,
            resolution_action=body.strategy,
            resolved_by=body.resolved_by
        )
        
        return ResolveAlertResponse(
            status=result["status"],
            message=result["message"]
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(f"❌ Error resolving alert: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/provisioning/status/{project_id}")
async def get_provisioning_status(project_id: str):
    """
    **Get Real-Time Provisioning Status**
    
    Returns overview of all devices and their provisioning state:
    - PROVISIONED (green): Hardware verified, IP assigned
    - BLOCKED_IDENTITY_MISMATCH (red): Wrong hardware detected
    - INVENTORY_UPDATED (yellow): Was corrected via UPDATE_INVENTORY
    - OVERRIDE_APPLIED (orange): Lead override applied (caution)
    - PENDING (grey): Waiting for power-on
    
    **Use Case:**
    Dashboard "Rack View" showing color-coded device status.
    """
    from google.cloud import firestore  # type: ignore
    
    firestore_client = get_firestore_client()
    
    # Get all devices from live_infrastructure collection
    devices_query = (
        firestore_client
        .collection("live_infrastructure")
        .where("projectId", "==", project_id)
        .stream()
    )
    
    devices = []
    status_summary = {
        "PROVISIONED": 0,
        "BLOCKED_IDENTITY_MISMATCH": 0,
        "INVENTORY_UPDATED": 0,
        "OVERRIDE_APPLIED": 0,
        "UNREACHABLE": 0
    }
    
    for doc in devices_query:
        device_data = doc.to_dict()
        status = device_data.get("status", "UNKNOWN")
        
        # Count status types
        if status in status_summary:
            status_summary[status] += 1
        
        devices.append({
            "deviceId": doc.id,
            "deviceName": device_data.get("deviceName"),
            "status": status,
            "location": device_data.get("location"),
            "assignedIp": device_data.get("assignedIp"),
            "identityVerified": device_data.get("identityVerified"),
            "serialNumberMatch": device_data.get("serialNumberMatch"),
            "expectedSerial": device_data.get("expectedSerial"),
            "detectedSerial": device_data.get("detectedSerial"),
            "alertId": device_data.get("alertId")
        })
    
    return {
        "projectId": project_id,
        "summary": status_summary,
        "devices": devices,
        "totalDevices": len(devices)
    }

# NEW: Tier Health Endpoints
@router.get("/tier-health/{project_id}/{tier}")
def get_tier_health(project_id: str, tier: str):
    """Get health status for a specific tier.
    
    Args:
        project_id: Project identifier
        tier: Tier name (BACKEND_FABRIC, STORAGE, COMPUTE)
    """
    from app.libs.dependency_manager import DependencyManager, Tier
    
    try:
        tier_enum = Tier(tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}")
    
    mgr = DependencyManager(project_id)
    health = mgr.get_tier_health(tier_enum)
    
    return health

@router.get("/cluster-readiness/{project_id}")
def get_cluster_readiness(project_id: str):
    """Get overall cluster readiness status with all tiers."""
    from app.libs.dependency_manager import DependencyManager
    
    mgr = DependencyManager(project_id)
    readiness = mgr.get_cluster_readiness()
    
    return readiness

@router.post("/emergency-override/{project_id}")
def emergency_override(project_id: str, body: EmergencyOverrideRequest):
    """Emergency override for tier dependency blocks.
    
    Requires CTO-level authorization token.
    Creates permanent audit trail.
    """
    from app.libs.dependency_manager import DependencyManager
    from google.cloud import firestore
    from datetime import datetime, timezone
    
    mgr = DependencyManager(project_id)
    
    # Validate override permission
    override_check = mgr.check_override_permission(
        device_tier=None,  # Not needed for this endpoint
        override_token=body.override_token
    )
    
    if not override_check["permitted"]:
        raise HTTPException(
            status_code=403,
            detail="Invalid override token. CTO authorization required."
        )
    
    # Create audit trail
    audit_ref = mgr.db.collection("override_audit").document()
    audit_ref.set({
        "project_id": project_id,
        "device_name": body.device_name,
        "reason": body.reason,
        "timestamp": datetime.now(timezone.utc),
        "override_token_used": True
    })
    
    # Update device to allow provisioning despite dependency block
    devices_ref = mgr.db.collection("live_infrastructure")
    query = devices_ref.where("deviceName", "==", body.device_name).where("project_id", "==", project_id)
    results = list(query.stream())
    
    if results:
        device_ref = results[0].reference
        device_ref.update({
            "override_active": True,
            "override_reason": body.reason,
            "override_timestamp": datetime.now(timezone.utc)
        })
        
        return {
            "status": "SUCCESS",
            "message": f"Emergency override activated for {body.device_name}",
            "audit_id": audit_ref.id
        }
    else:
        raise HTTPException(status_code=404, detail="Device not found")

# NEW: IP Allocation Preview Endpoint
@router.get("/ip-allocation-preview/{project_id}")
def get_ip_allocation_preview(project_id: str):
    """Get preview of IP allocations before deployment.
    
    Shows all planned GPU IP assignments with conflict detection.
    """
    from app.libs.cluster_topology import ClusterTopology
    from app.libs.ip_schema_orchestrator import IPSchemaOrchestrator
    from app.libs.ip_conflict_detector import IPConflictDetector
    from google.cloud import firestore
    
    # Load topology from Firestore
    db = get_firestore_client()
    config_ref = db.collection("cluster_configs").document(project_id)
    config_doc = config_ref.get()
    
    if not config_doc.exists:
        raise HTTPException(status_code=404, detail="Cluster config not found")
    
    config_data = config_doc.to_dict()
    topology_data = config_data.get("topologyProfile", {})
    
    # Create topology
    topology = ClusterTopology(
        G=topology_data.get("G", 8),
        N=topology_data.get("N", 2),
        S=topology_data.get("S", 16),
        R=topology_data.get("R", 8),
        P=topology_data.get("P", 2),
        L=topology_data.get("L", 8),
        SU_ID=topology_data.get("SU_ID", 1)
    )
    
    # Create orchestrator and detector
    orchestrator = IPSchemaOrchestrator(topology)
    detector = IPConflictDetector(topology, orchestrator)
    
    # Run conflict scan
    scan_results = detector.run_full_scan()
    
    # Generate sample allocations (first 100 for preview)
    sample_allocations = []
    count = 0
    for rack_idx in range(1, min(topology.R + 1, 3)):  # First 2 racks
        for server_idx in range(1, min(topology.S + 1, 5)):  # First 4 servers
            for gpu_idx in range(min(topology.G, 2)):  # First 2 GPUs
                for tail_idx in range(topology.N):
                    ip_data = orchestrator.generate_gpu_ip(
                        rack_idx, server_idx, gpu_idx, tail_idx
                    )
                    sample_allocations.append({
                        "device": f"Rack{rack_idx}-Srv{server_idx}-GPU{gpu_idx}-Tail{tail_idx}",
                        "gpu_ip": ip_data["gpu_ip"],
                        "switch_ip": ip_data["switch_ip"],
                        "subnet": ip_data["subnet"],
                        "plane": tail_idx,
                        "global_rack": topology.get_global_rack_id(rack_idx)
                    })
                    count += 1
                    if count >= 100:
                        break
                if count >= 100:
                    break
            if count >= 100:
                break
        if count >= 100:
            break
    
    return {
        "total_ips": scan_results["total_ips_allocated"],
        "ip_allocations": sample_allocations,
        "conflicts": scan_results["conflicts"],
        "status": scan_results["status"],
        "summary": {
            "total_conflicts": scan_results["total_conflicts"],
            "critical_conflicts": scan_results["critical_conflicts"],
            "conflicts_by_type": scan_results["conflicts_by_type"]
        }
    }
