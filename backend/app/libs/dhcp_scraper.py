"""
DHCP Scraper for Deterministic Switch Provisioning

Listens for DHCP DISCOVER packets from switches powering on,
matches them against Day 0 Firestore inventory, and assigns
deterministic private IPs based on physical rack location.

Critical for preventing "wrong cable" errors in GPU clusters where
a single misconfigured switch can take down a $50M deployment.

**NEW: Topology-Aware Provisioning**
The scraper now validates switch hardware against cluster topology:
- Ensures switch has enough ports for its role
- Injects topology DNA into GPU-aware ZTP generation
- Fails fast on topology violations

Workflow:
1. Monitor DHCP server logs for new DISCOVER packets
2. Extract MAC address from request
3. Query switch via SNMP/SSH to get serial number (or receive discovery callback)
4. Match against Firestore inventory
5. Validate topology compatibility
6. Generate GPU-aware ZTP script with topology injection
7. Assign deterministic IP or raise mismatch alert

Example:
    scraper = DHCPScraper(project_id="my-cluster")
    result = scraper.process_dhcp_discover("00:1A:2B:3C:4D:5E")
    if result["status"] == "BLOCKED":
        # Alert Installation Lead to remediate
"""

import os
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import json
import re
from google.cloud import firestore  # type: ignore
from google.oauth2 import service_account
import databutton as db
from app.libs.topology_profile import TopologyProfile
from app.libs.gpu_to_leaf_mapper import GPUToLeafMapper
from app.libs.multi_su_test_suite import MultiSUValidator, SUIDExtractor
from app.libs.dependency_manager import DependencyManager, Tier
from app.libs.firestore_scoping import get_scoped_collection
from app.libs.audit_logger import AuditLogger
from app.libs.switch_model_database import SwitchModelDatabase
from app.libs.datasheet_fetcher import DatasheetFetcher
from app.libs.jit_ztp_generator import JITZTPGenerator
from app.libs.ip_schema_orchestrator import IPSchemaOrchestrator


class DHCPScraper:
    """Scrapes DHCP requests and matches hardware against Day 0 plan.
    
    The DHCPScraper acts as the "midwife" for the network, bringing it into
    existence one deterministic IP assignment at a time.
    
    Why Deterministic IPs Matter:
    - Prevents configuration drift (wrong config pushed to wrong device)
    - Enables predictable SSH access from border switch
    - Creates audit trail of hardware-to-location mapping
    - Catches technician errors before automation runs
    
    Firestore Collections (customer-scoped):
    - customers/{customer_id}/extracted_devices: Day 0 planned inventory
    - customers/{customer_id}/infrastructure: Real-time provisioning status
    - customers/{customer_id}/provisioning_alerts: Mismatch alerts
    """
    
    def __init__(self, project_id: str, customer_id: str):
        """Initialize DHCP scraper for a specific project.
        
        Args:
            project_id: Firestore project ID
            customer_id: Customer ID for data isolation
        """
        self.project_id = project_id
        self.customer_id = customer_id
        creds = service_account.Credentials.from_service_account_info(
            json.loads(os.environ.get("FIREBASE_ADMIN_CREDENTIALS"))
        )
        self.db = firestore.Client(credentials=creds)
        self.firestore_client = self.db  # Alias for backward compatibility
        
        # Initialize dependencies
        self.switch_db = SwitchModelDatabase()
        self.datasheet_fetcher = DatasheetFetcher()
        self.ztp_generator = JITZTPGenerator(self.switch_db)
        self.dependency_mgr = DependencyManager(project_id, self.db, customer_id=self.customer_id)
        self.audit_logger = AuditLogger(self.db)
        
        print(f"⚙️ DHCPScraper initialized for project {project_id}, customer {customer_id}")
    
    def process_dhcp_discover(self, mac_address: str, vendor_class: Optional[str] = None) -> Dict:
        """Main entry point when DHCP DISCOVER packet is detected.
        
        This is called by the DHCP server webhook or log watcher when
        a new switch sends a DHCP request during initial power-on.
        
        Args:
            mac_address: MAC address from DHCP request (e.g., "00:1A:2B:3C:4D:5E")
            vendor_class: DHCP Option 60 (vendor class identifier)
                         Example: "Arista;7060X4", "NVIDIA;QM9700"
            
        Returns:
            Dict with keys:
            - status: "SUCCESS" | "BLOCKED" | "UNKNOWN" | "UNREACHABLE"
            - device_name: Planned device name (if found)
            - assigned_ip: Deterministic management IP (if match successful)
            - location: Rack/U-Position string
            - alert_id: Firestore alert ID (if mismatch detected)
            - reason: Error reason (if blocked)
            - ztp_url: URL for ZTP script download (if success)
        
        Example:
            >>> scraper.process_dhcp_discover(
            ...     mac_address="00:1A:2B:3C:4D:5E",
            ...     vendor_class="Arista;7060X4"
            ... )
            {"status": "SUCCESS", "assigned_ip": "10.0.1.50", "ztp_url": "https://...", ...}
        """
        print(f"\n{'='*70}")
        print(f"🔍 NEW SWITCH DISCOVERY: MAC {mac_address}")
        if vendor_class:
            print(f"🏷️ Vendor Class (Option 60): {vendor_class}")
        print(f"{'='*70}")
        
        # Step 1: Find the planned device in Firestore
        planned_device = self._lookup_planned_device(mac_address)
        
        if not planned_device:
            return self._handle_unknown_device(mac_address)
        
        # Step 2: Extract vendor and model from vendor_class
        vendor, model = self._parse_vendor_class(vendor_class, planned_device)
        
        # Step 3: Wait for switch to fully boot, then query serial number
        detected_serial = self._query_switch_serial(mac_address)
        
        if not detected_serial:
            return self._handle_unreachable_switch(mac_address, planned_device)
        
        # Step 4: Verify identity (The "Perfect Match" Check)
        expected_serial = planned_device.get("hardwareInfo", {}).get("serialNumber")
        
        if detected_serial == expected_serial:
            return self._handle_identity_match(planned_device, mac_address, detected_serial, vendor, model)
        else:
            return self._handle_identity_mismatch(planned_device, detected_serial)
    
    def handle_discovery_callback(
        self, 
        mac_address: str, 
        detected_serial: str,
        vendor: Optional[str] = None,
        model: Optional[str] = None
    ) -> Dict:
        """Handle Stage 1 discovery callback from switch reporting its serial number.
        
        This is the NEW entry point that replaces _query_switch_serial().
        Instead of remotely querying an unconfigured switch, we let the switch
        report its own serial number via the discovery script.
        
        Workflow:
        1. Switch executes discovery script (sent via DHCP Option 67)
        2. Script extracts serial number locally (dmidecode)
        3. Script POSTs to /ztp/discovery with MAC + serial
        4. This method verifies identity against Firestore
        5. If match → generate full ZTP config and mark DISCOVERY_VERIFIED
        6. If mismatch → create alert and block provisioning
        
        Args:
            mac_address: MAC address reported by switch
            detected_serial: Serial number extracted by discovery script
            vendor: Optional vendor name from dmidecode
            model: Optional model name from dmidecode
            
        Returns:
            Same dict format as process_dhcp_discover()
        """
        print(f"\n{'='*70}")
        print(f"🔍 DISCOVERY CALLBACK: {mac_address}")
        print(f"   Reported Serial: {detected_serial}")
        if vendor and model:
            print(f"   Reported Vendor/Model: {vendor} {model}")
        print(f"{'='*70}")
        
        # Step 1: Lookup planned device
        planned_device = self._lookup_planned_device(mac_address)
        
        if not planned_device:
            return self._handle_unknown_device(mac_address)
        
        # Step 2: Extract vendor/model from planned device if not provided
        if not vendor or not model:
            hw_info = planned_device.get("hardwareInfo", {})
            vendor = vendor or hw_info.get("vendor")
            model = model or hw_info.get("model")
        
        # Step 3: Verify identity (critical check)
        expected_serial = planned_device.get("hardwareInfo", {}).get("serialNumber")
        
        if detected_serial == expected_serial:
            return self._handle_identity_match(planned_device, mac_address, detected_serial, vendor, model)
        else:
            return self._handle_identity_mismatch(planned_device, detected_serial)
    
    def _lookup_planned_device(self, mac_address: str) -> Optional[Dict]:
        """Query Firestore for device with this MAC address from Day 0 extraction.
        
        Searches the extracted_devices collection for a device where the
        hardwareInfo.macAddress matches the detected MAC.
        
        Args:
            mac_address: MAC address to search for
            
        Returns:
            Device document dict with firestore_doc_id added, or None if not found
        """
        # Normalize MAC address format (uppercase, colon-separated)
        mac_normalized = mac_address.upper().replace("-", ":").replace(".", ":")
        
        # Query extracted_devices collection (customer-scoped)
        query = (
            get_scoped_collection(self.db, self.customer_id, "extracted_devices")
            .where("projectId", "==", self.project_id)
            .where("hardwareInfo.macAddress", "==", mac_normalized)
            .limit(1)
            .stream()
        )
        
        for doc in query:
            print(f"✅ Found planned device: {doc.id}")
            device_data = doc.to_dict()
            device_data["firestore_doc_id"] = doc.id
            return device_data
        
        print(f"❌ No planned device found with MAC {mac_normalized}")
        return None
    
    def _query_switch_serial(self, mac_address: str, timeout: int = 60) -> Optional[str]:
        """Wait for switch to boot and query its serial number via SNMP or SSH.
        
        In production, this would:
        1. Wait for switch to respond to ping (with timeout)
        2. Try SNMP first (faster): snmpget -v2c -c public <temp_ip> 1.3.6.1.4.1.9.3.6.1.0
        3. Fallback to SSH: ssh admin@<temp_ip> "show version | grep Serial"
        4. Parse response to extract serial number
        
        For development/testing, we simulate with a lookup table.
        
        Args:
            mac_address: MAC address of switch to query
            timeout: Max seconds to wait for switch to boot
            
        Returns:
            Serial number string, or None if unreachable
        """
        print(f"⏳ Waiting for switch {mac_address} to boot and respond to serial query...")
        
        # SIMULATION: In production, replace with actual SNMP/SSH query
        # For demo purposes, we use a mock mapping
        mock_serial_map = {
            "00:1B:21:D9:56:E1": "NVDA-QM9700-SP01-2024",
            "00:1B:21:D9:56:E2": "NVDA-QM9700-LF01-2024",
            "00:1C:73:A8:77:F3": "ARIS-7280SR3-FE01-2024",
            "00:1E:BD:C4:88:D4": "CSCO-C9300-OOB01-2024",
            "00:1B:21:D9:56:E3": "NVDA-QM9700-SP02-2024",  # This will be correct
            "00:1B:21:D9:56:E4": "WRONG-SERIAL-NUMBER",  # This will trigger mismatch
        }
        
        detected_serial = mock_serial_map.get(mac_address)
        
        if detected_serial:
            print(f"📡 Detected Serial: {detected_serial}")
        else:
            print(f"⚠️ Switch not responding to serial query (timeout after {timeout}s)")
        
        return detected_serial
    
    def _handle_identity_match(
        self, 
        planned_device: Dict, 
        mac_address: str, 
        detected_serial: str, 
        vendor: str, 
        model: str
    ) -> Dict:
        """Handle successful identity verification."""
        device_name = planned_device.get("deviceName", mac_address)
        device_role = planned_device.get("role", "UNKNOWN")
        network_meta = planned_device.get("networkMetadata", {})
        assigned_ip = network_meta.get("managementIp") or network_meta.get("ipAddress") or "10.0.0.254"
        location_data = planned_device.get("location", {})
        if isinstance(location_data, str):
            location = location_data
            rack = location_data
            u_pos = "UNKNOWN"
        else:
            rack = location_data.get("rack", "UNKNOWN")
            u_pos = location_data.get("uPosition", "UNKNOWN")
            location = f"{rack}/{u_pos}"
        
        print(f"✅ Identity match successful for {device_name}")
        
        # Step 1: Multi-SU validation (existing from MYA-151)
        rack_match = re.search(r"Rack[\s-]*(\d+)", str(location), re.IGNORECASE)
        
        if rack_match:
            physical_rack_id = int(rack_match.group(1))
            
            # Load topology
            config_ref = self.db.collection("cluster_configs").document(self.project_id)
            config_doc = config_ref.get()
            
            if config_doc.exists:
                config_data = config_doc.to_dict()
                topology_data = config_data.get("topologyProfile", {})
                
                from app.libs.cluster_topology import ClusterTopology
                topology = ClusterTopology(
                    G=topology_data.get("G", 8),
                    N=topology_data.get("N", 2),
                    S=topology_data.get("S", 16),
                    R=topology_data.get("R", 8),
                    P=topology_data.get("P", 2),
                    L=topology_data.get("L", 8),
                    SU_ID=topology_data.get("SU_ID", 1)
                )
                
                # Check Multi-SU boundaries
                requested_hostname = device_name
                
                validation_result = MultiSUValidator.validate_dhcp_request(
                    requested_hostname=requested_hostname,
                    physical_rack_id=physical_rack_id,
                    topology=topology
                )
                
                if not validation_result["is_valid"]:
                    return self._handle_cross_su_violation(
                        planned_device=planned_device,
                        mac_address=mac_address,
                        violation_details=validation_result
                    )
        
        # Step 2: NEW - Check tier dependencies
        tier_check = self._check_tier_dependencies(device_role, device_name)
        
        if not tier_check["allowed"]:
            print(f"❌ TIER DEPENDENCY BLOCK: {device_name}")
            print(f"   Reason: {tier_check['reason']}")
            
            # Update device status
            devices_ref = get_scoped_collection(self.db, self.customer_id, "live_infrastructure")
            query = devices_ref.where("macAddress", "==", mac_address).where("project_id", "==", self.project_id)
            results = list(query.stream())
            
            if results:
                device_ref = results[0].reference
                device_ref.update({
                    "status": "BLOCKED_TIER_DEPENDENCY",
                    "blocking_tiers": tier_check.get("blocking_tiers", []),
                    "last_updated": datetime.now(timezone.utc)
                })
            
            return {
                "status": "BLOCKED",
                "reason": tier_check["reason"],
                "blocking_tiers": tier_check.get("blocking_tiers", [])
            }
        
        # Step 3 & 4: Generate ZTP and assign IP (existing logic)
        # Extract switch role (BACKEND_LEAF, FRONTEND_SPINE, etc.)
        role = self._determine_switch_role(planned_device)
        
        # NEW: Extract topology and validate Multi-SU boundaries
        topology_dict = planned_device.get('topologyProfile')
        if topology_dict:
            try:
                # Parse physical rack ID from location
                physical_rack_id = None
                if isinstance(rack, str):
                    # Extract rack number from strings like "Rack-01" or "RACK_03"
                    rack_match = re.search(r'(\d+)', rack)
                    if rack_match:
                        physical_rack_id = int(rack_match.group(1))
                elif isinstance(rack, int):
                    physical_rack_id = rack
                
                if physical_rack_id and device_name:
                    # Build ClusterTopology from profile
                    topology = ClusterTopology(
                        G=topology_dict.get('gpus_per_server', 8),
                        N=topology_dict.get('nics_per_gpu', 2),
                        S=topology_dict.get('servers_per_rack', 16),
                        R=topology_dict.get('racks_per_su', 8),
                        P=topology_dict.get('planes', 2),
                        L=topology_dict.get('leafs_per_plane', 8),
                        SU_ID=topology_dict.get('su_id', 1),
                        SU_COUNT=topology_dict.get('su_count', 1),
                        cable_split=topology_dict.get('cable_split', 1)
                    )
                    
                    # Validate Multi-SU boundary
                    is_valid, violation_msg = MultiSUValidator.validate_dhcp_request(
                        requested_hostname=device_name,
                        physical_rack_id=physical_rack_id,
                        topology=topology
                    )
                    
                    if not is_valid:
                        print("\n🚨 CROSS-SU CONTAMINATION DETECTED!")
                        print(f"   {violation_msg}")
                        return self._handle_cross_su_violation(
                            planned_device=planned_device,
                            detected_serial=detected_serial,
                            violation_message=violation_msg,
                            physical_rack_id=physical_rack_id,
                            requested_hostname=device_name
                        )
                    else:
                        print("\n✅ MULTI-SU BOUNDARY CHECK PASSED")
                        print(f"   Switch '{device_name}' is in correct SU (SU-{topology.SU_ID})")
                
            except Exception as e:
                print(f"⚠️ Multi-SU validation failed: {e}")
                print("   Continuing without SU boundary check...")
        
        # Existing topology validation code
        topology_dict = planned_device.get('topologyProfile')
        if not topology_dict:
            print("⚠️ No topology profile found - falling back to legacy mode")
            return self._handle_legacy_provisioning(
                planned_device, detected_serial, vendor, model, role, assigned_ip
            )
        
        try:
            topology_profile = TopologyProfile.from_dict(topology_dict)
            topology_profile.validate()
            
            # Validate hardware-topology compatibility
            if vendor and model:
                is_compatible, violation = self._validate_topology_compatibility(
                    vendor, model, topology_profile, role
                )
                
                if not is_compatible:
                    return self._handle_topology_violation(
                        planned_device, violation
                    )
            
            # Generate GPU-aware ZTP script
            ztp_url = self._generate_gpu_aware_ztp(
                planned_device, topology_profile, vendor, model, role, assigned_ip
            )
            
        except Exception as e:
            print(f"⚠️ Topology validation failed: {e}")
            print("   Falling back to legacy ZTP")
            return self._handle_legacy_provisioning(
                planned_device, detected_serial, vendor, model, role, assigned_ip
            )
        
        # Update Firestore: Mark device as PROVISIONED
        firestore_data = {
            "projectId": self.project_id,
            "deviceName": device_name,
            "status": "PROVISIONED",
            "provisionedAt": firestore.SERVER_TIMESTAMP,
            "assignedIp": assigned_ip,
            "identityVerified": True,
            "serialNumberMatch": "VERIFIED",
            "location": location,
            "detectedSerial": detected_serial,
            "vendor": vendor,
            "model": model,
            "role": role,
            "topologyValidated": True
        }
        
        if ztp_url:
            firestore_data["ztpUrl"] = ztp_url
            firestore_data["ztpGenerated"] = True
            firestore_data["ztpMode"] = "GPU_AWARE"
        
        get_scoped_collection(self.db, self.customer_id, "live_infrastructure").document(
            planned_device["firestore_doc_id"]
        ).set(firestore_data, merge=True)
        
        # Push DHCP static reservation
        self._assign_static_ip(
            planned_device.get("hardwareInfo", {}).get("macAddress"), 
            assigned_ip, 
            device_name,
            ztp_url
        )
        
        print(f"🚀 DHCP static lease created: {assigned_ip}")
        if ztp_url:
            print("📦 ZTP URL will be provided via DHCP Option 67")
        
        # NEW: For COMPUTE tier nodes, schedule K8s join after OS install completes
        if role == "GPU_NODE" or role == "COMPUTE_NODE" or (device_role and "COMPUTE" in device_role.upper()):
            print("\n🔗 COMPUTE NODE DETECTED: Scheduling K8s auto-join")
            print("   Node will join K8s cluster after OS installation completes")
            print(f"   Hostname: {device_name}")
            print(f"   IP: {assigned_ip}")
            
            # NOTE: In production, this would be triggered AFTER OS install completes.
            # For now, we mark it in Firestore and the ZTP completion webhook will trigger it.
            firestore_data["k8s_join_pending"] = True
            firestore_data["k8s_expected_gpus"] = 8  # H100 nodes have 8 GPUs
            
            # Re-update Firestore with K8s join metadata
            get_scoped_collection(self.db, self.customer_id, "live_infrastructure").document(
                planned_device["firestore_doc_id"]
            ).update({
                "k8s_join_pending": True,
                "k8s_expected_gpus": 8
            })
        
        result = {
            "status": "SUCCESS",
            "device_name": device_name,
            "assigned_ip": assigned_ip,
            "location": f"{rack}/{u_pos}"
        }
        
        if ztp_url:
            result["ztp_url"] = ztp_url
            result["ztp_ready"] = True
            result["ztp_mode"] = "GPU_AWARE"
            
        # Log to Enterprise Audit Trail
        self.audit_logger.log_action(
            user_email="system@techtalk.ai",
            customer_id=self.customer_id,
            action="provisioned_device",
            details={
                "device_name": device_name,
                "mac_address": mac_address,
                "assigned_ip": assigned_ip,
                "role": role,
                "ztp_generated": bool(ztp_url)
            },
            project_id=self.project_id
        )
        
        return result
    
    def _validate_topology_compatibility(
        self,
        vendor: str,
        model: str,
        topology_profile: TopologyProfile,
        role: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate switch hardware against topology requirements.
        
        Fail-fast check to prevent provisioning incompatible hardware.
        
        Args:
            vendor: Switch vendor
            model: Switch model
            topology_profile: Cluster topology profile
            role: Switch role (BACKEND_LEAF, BACKEND_SPINE, etc.)
            
        Returns:
            Tuple of (is_compatible, violation_reason)
        """
        print("\n🔍 Validating topology compatibility...")
        
        # Get hardware specs
        try:
            specs = self.switch_db.get_or_learn_specs(
                vendor, model, self.datasheet_fetcher
            )
            port_count = specs['data_port_count']
            
            print(f"   Switch: {vendor} {model}")
            print(f"   Available ports: {port_count}")
            
        except Exception as e:
            return False, f"Failed to get hardware specs: {e}"
        
        # Calculate required ports for this role
        required_ports = topology_profile.calculate_required_ports(role)
        
        print(f"   Required ports for {role}: {required_ports}")
        
        if role == "BACKEND_LEAF":
            # Each leaf connects to all servers in all racks
            if port_count < required_ports:
                return False, (
                    f"BACKEND_LEAF requires {required_ports} ports "
                    f"({topology_profile.servers_per_rack} servers/rack × "
                    f"{topology_profile.racks_per_su} racks), "
                    f"but {model} only has {port_count} ports. "
                    f"Consider reducing servers per rack or using higher-port-count switch."
                )
        
        elif role == "BACKEND_SPINE":
            # Each spine connects to all leafs in all planes
            if port_count < required_ports:
                return False, (
                    f"BACKEND_SPINE requires {required_ports} ports "
                    f"({topology_profile.leafs_per_plane} leafs/plane × "
                    f"{topology_profile.planes} planes), "
                    f"but {model} only has {port_count} ports. "
                    f"Consider reducing leafs per plane or using higher-radix spine."
                )
        
        print("✅ Topology compatibility validated")
        return True, None
    
    def _generate_gpu_aware_ztp(
        self,
        planned_device: Dict,
        topology_profile: TopologyProfile,
        vendor: str,
        model: str,
        role: str,
        mgmt_ip: str
    ) -> Optional[str]:
        """Generate GPU-aware ZTP script with topology injection.
        
        Args:
            planned_device: Device document from Firestore
            topology_profile: Cluster topology profile
            vendor: Switch vendor
            model: Switch model
            role: Switch role
            mgmt_ip: Management IP
            
        Returns:
            ZTP download URL or None if generation fails
        """
        device_name = planned_device.get("deviceName")
        
        # Check if this is a backend leaf (GPU-aware provisioning)
        if role == "BACKEND_LEAF":
            # Extract plane and leaf IDs from planned device
            plane_id = planned_device.get("planeId")
            leaf_id = planned_device.get("leafId")
            
            if plane_id is None or leaf_id is None:
                print("⚠️ Missing planeId/leafId for BACKEND_LEAF - falling back to legacy")
                return self._generate_legacy_ztp(device_name, role, vendor, model, mgmt_ip)
            
            try:
                print("\n⚙️ Generating GPU-aware ZTP configuration with GLOBAL IP SCHEMA...")
                
                # Convert topology profile to ClusterTopology
                topology = topology_profile.to_cluster_topology()
                mapper = GPUToLeafMapper(topology)
                
                # Create IPSchemaOrchestrator for global IP allocation (multi-SU aware)
                ip_orchestrator = IPSchemaOrchestrator(topology)
                
                # Inject orchestrator into ZTP generator for this request
                self.ztp_generator.ip_orchestrator = ip_orchestrator
                
                print(f"   Multi-SU Mode: SU {topology.SU_ID}/{topology.SU_COUNT}")
                print("   Global IP Schema: 100.{126+P}.{global_rack}.{gpu_offset}")
                
                # Generate full GPU-aware config
                ztp_script = self.ztp_generator.generate_full_config(
                    switch_id=device_name,
                    plane_id=plane_id,
                    leaf_id=leaf_id,
                    vendor=vendor,
                    model=model,
                    mgmt_ip=mgmt_ip,
                    topology=topology,
                    mapper=mapper,
                    fetcher=self.datasheet_fetcher
                )
                
                # Save script to storage
                storage_key = self.ztp_generator.save_ztp_script(ztp_script)
                
                # Construct public URL
                base_url = "https://juniortechbot.riff.works/techassist"
                ztp_url = self.ztp_generator.get_ztp_url(storage_key, base_url)
                
                print(f"✅ GPU-aware ZTP script ready: {ztp_url}")
                print(f"   Configured ports: {ztp_script['configured_ports']}")
                print(f"   Plane: {plane_id}, Leaf: {leaf_id}")
                print("   IP Schema: Global (Multi-SU aware)")
                
                return ztp_url
                
            except Exception as e:
                print(f"⚠️ Failed to generate GPU-aware ZTP: {e}")
                print("   Falling back to legacy ZTP")
                return self._generate_legacy_ztp(device_name, role, vendor, model, mgmt_ip)
        
        else:
            # For non-BACKEND_LEAF roles, use legacy provisioning
            return self._generate_legacy_ztp(device_name, role, vendor, model, mgmt_ip)
    
    def _generate_legacy_ztp(
        self,
        device_name: str,
        role: str,
        vendor: str,
        model: str,
        mgmt_ip: str
    ) -> Optional[str]:
        """Generate legacy (sequential port) ZTP script.
        
        Used for:
        - Management/OOB networks
        - Frontend (Ethernet) networks
        - Spine switches
        - Fallback when topology is unavailable
        
        Args:
            device_name: Device hostname
            role: Switch role
            vendor: Switch vendor
            model: Switch model
            mgmt_ip: Management IP
            
        Returns:
            ZTP download URL or None
        """
        try:
            print("\n⚙️ Generating legacy ZTP configuration...")
            
            ztp_script = self.ztp_generator.generate_ztp_script(
                switch_id=device_name,
                role=role,
                vendor=vendor,
                model=model,
                mgmt_ip=mgmt_ip,
                fetcher=self.datasheet_fetcher
            )
            
            storage_key = self.ztp_generator.save_ztp_script(ztp_script)
            base_url = "https://juniortechbot.riff.works/techassist"
            ztp_url = self.ztp_generator.get_ztp_url(storage_key, base_url)
            
            print(f"✅ Legacy ZTP script ready: {ztp_url}")
            return ztp_url
            
        except Exception as e:
            print(f"⚠️ Failed to generate ZTP script: {e}")
            return None
    
    def _handle_legacy_provisioning(
        self,
        planned_device: Dict,
        detected_serial: str,
        vendor: str,
        model: str,
        role: str,
        assigned_ip: str
    ) -> Dict:
        """Handle provisioning without topology validation (legacy mode).
        
        Used when topology profile is missing or invalid.
        """
        device_name = planned_device.get("deviceName")
        location = planned_device.get("location", {})
        rack = location.get("rack", "UNKNOWN")
        u_pos = location.get("uPosition", "UNKNOWN")
        
        # Generate legacy ZTP
        ztp_url = None
        if vendor and model:
            ztp_url = self._generate_legacy_ztp(
                device_name, role, vendor, model, assigned_ip
            )
        
        # Update Firestore
        firestore_data = {
            "projectId": self.project_id,
            "deviceName": device_name,
            "status": "PROVISIONED",
            "provisionedAt": firestore.SERVER_TIMESTAMP,
            "assignedIp": assigned_ip,
            "identityVerified": True,
            "serialNumberMatch": "VERIFIED",
            "location": location,
            "detectedSerial": detected_serial,
            "vendor": vendor,
            "model": model,
            "role": role,
            "topologyValidated": False,
            "ztpMode": "LEGACY"
        }
        
        if ztp_url:
            firestore_data["ztpUrl"] = ztp_url
            firestore_data["ztpGenerated"] = True
        
        get_scoped_collection(self.db, self.customer_id, "live_infrastructure").document(
            planned_device["firestore_doc_id"]
        ).set(firestore_data, merge=True)
        
        # Assign DHCP
        self._assign_static_ip(
            planned_device.get("hardwareInfo", {}).get("macAddress"),
            assigned_ip,
            device_name,
            ztp_url
        )
        
        result = {
            "status": "SUCCESS",
            "device_name": device_name,
            "assigned_ip": assigned_ip,
            "location": f"{rack}/{u_pos}",
            "ztp_mode": "LEGACY"
        }
        
        if ztp_url:
            result["ztp_url"] = ztp_url
            result["ztp_ready"] = True
        
        return result
    
    def _handle_topology_violation(
        self,
        planned_device: Dict,
        violation_reason: str
    ) -> Dict:
        """Handle topology compatibility violation.
        
        Blocks provisioning and creates alert.
        
        Args:
            planned_device: Device document
            violation_reason: Description of topology violation
            
        Returns:
            Blocked result dict
        """
        device_name = planned_device.get("deviceName")
        location = planned_device.get("location", {})
        rack = location.get("rack", "UNKNOWN")
        u_pos = location.get("uPosition", "UNKNOWN")
        mac_address = planned_device.get("hardwareInfo", {}).get("macAddress")
        
        print("\n❌ TOPOLOGY VIOLATION DETECTED")
        print(f"   Device: {device_name}")
        print(f"   Location: {rack} / {u_pos}")
        print(f"   Reason: {violation_reason}")
        print("   ⚠️ PROVISIONING HALTED")
        
        # Create CRITICAL alert
        alert_ref = get_scoped_collection(self.db, self.customer_id, "provisioning_alerts").add({
            "projectId": self.project_id,
            "severity": "CRITICAL",
            "type": "TOPOLOGY_VIOLATION",
            "status": "UNRESOLVED",
            "location": {
                "rack": rack,
                "uPosition": u_pos
            },
            "planned": {
                "deviceName": device_name
            },
            "detected": {
                "macAddress": mac_address
            },
            "message": f"Topology violation at {rack}/{u_pos}: {violation_reason}",
            "impact": "ZTP generation halted. Switch hardware incompatible with cluster topology.",
            "recommendation": "Replace switch with compatible model or adjust topology profile.",
            "violationReason": violation_reason,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "resolvedAt": None
        })
        
        # Mark device as BLOCKED
        get_scoped_collection(self.db, self.customer_id, "live_infrastructure").document(
            planned_device["firestore_doc_id"]
        ).set({
            "projectId": self.project_id,
            "deviceName": device_name,
            "status": "BLOCKED_TOPOLOGY_VIOLATION",
            "blockedAt": firestore.SERVER_TIMESTAMP,
            "alertId": alert_ref[1].id,
            "topologyValidated": False,
            "violationReason": violation_reason,
            "location": location
        }, merge=True)
        
        return {
            "status": "BLOCKED",
            "alert_id": alert_ref[1].id,
            "reason": "TOPOLOGY_VIOLATION",
            "location": f"{rack}/{u_pos}",
            "violation": violation_reason
        }

    def _determine_switch_role(self, planned_device: Dict) -> str:
        """Determine switch role from device metadata.
        
        Looks for role indicators in:
        - deviceType field
        - deviceName patterns (SPINE, LEAF, CORE)
        - networkMetadata.tier
        
        Args:
            planned_device: Device document from Firestore
            
        Returns:
            Role string (e.g., "BACKEND_LEAF", "FRONTEND_SPINE")
        """
        device_name = planned_device.get("deviceName", "").upper()
        device_type = planned_device.get("deviceType", "").upper()
        tier = planned_device.get("networkMetadata", {}).get("tier", "").upper()
        
        # Detect plane (Backend vs Frontend)
        is_backend = any(x in device_name or x in device_type for x in ["IB", "INFINIBAND", "BACKEND", "GPU"])
        is_frontend = any(x in device_name or x in device_type for x in ["ETH", "ETHERNET", "FRONTEND", "STORAGE"])
        
        # Detect tier
        is_leaf = "LEAF" in device_name or "LEAF" in tier or "TOR" in device_name
        is_spine = "SPINE" in device_name or "SPINE" in tier
        is_core = "CORE" in device_name or "CORE" in tier
        
        # Construct role
        if is_backend:
            plane = "BACKEND"
        elif is_frontend:
            plane = "FRONTEND"
        else:
            plane = "OOB"  # Out of-band management
        
        if is_leaf:
            tier_name = "LEAF"
        elif is_spine:
            tier_name = "SPINE"
        elif is_core:
            tier_name = "CORE"
        else:
            tier_name = "LEAF"  # Default to leaf
        
        role = f"{plane}_{tier_name}"
        return role
    
    def _handle_identity_mismatch(self, planned_device: Dict, detected_serial: str) -> Dict:
        """❌ CRITICAL ERROR: Wrong hardware at this location.
        
        Halt IP assignment and create alert for Installation Lead.
        
        This is the "Holy Grail" protection - prevents pushing wrong
        configuration to wrong hardware, which could brick devices or
        create network loops that take down the entire cluster.
        
        Args:
            planned_device: Device document from Firestore
            detected_serial: Serial number queried from live hardware (wrong)
            
        Returns:
            Blocked result dict with alert_id and mismatch details
        """
        device_name = planned_device.get("deviceName")
        expected_serial = planned_device.get("hardwareInfo", {}).get("serialNumber")
        location = planned_device.get("location", {})
        rack = location.get("rack", "UNKNOWN")
        u_pos = location.get("uPosition", "UNKNOWN")
        mac_address = planned_device.get("hardwareInfo", {}).get("macAddress")
        
        print(f"\n{'❌ IDENTITY MISMATCH DETECTED'}")
        print(f"   Location: {rack} / {u_pos}")
        print(f"   Expected Device: {device_name}")
        print(f"   Expected Serial: {expected_serial}")
        print(f"   Detected Serial: {detected_serial}")
        print("   ⚠️ IP ASSIGNMENT HALTED")
        
        # Create CRITICAL alert in Firestore
        alert_ref = get_scoped_collection(self.db, self.customer_id, "provisioning_alerts").add({
            "projectId": self.project_id,
            "severity": "CRITICAL",
            "type": "IDENTITY_MISMATCH",
            "status": "UNRESOLVED",
            "location": {
                "rack": rack,
                "uPosition": u_pos
            },
            "planned": {
                "deviceName": device_name,
                "serialNumber": expected_serial
            },
            "detected": {
                "serialNumber": detected_serial,
                "macAddress": mac_address
            },
            "message": f"Technician Error: Switch at {rack}/{u_pos} has Serial {detected_serial}, but plan expected {expected_serial}",
            "impact": "IP assignment halted. Configuration automation blocked to prevent wrong config being pushed to wrong hardware.",
            "recommendation": "Verify physical switch location or update inventory to match reality. DO NOT override unless you are certain.",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "resolvedAt": None,
            "resolvedBy": None,
            "resolutionAction": None
        })
        
        # Mark device as BLOCKED in live_infrastructure
        get_scoped_collection(self.db, self.customer_id, "live_infrastructure").document(
            planned_device["firestore_doc_id"]
        ).set({
            "projectId": self.project_id,
            "deviceName": device_name,
            "status": "BLOCKED_IDENTITY_MISMATCH",
            "blockedAt": firestore.SERVER_TIMESTAMP,
            "alertId": alert_ref[1].id,
            "identityVerified": False,
            "serialNumberMatch": "MISMATCH",
            "location": location,
            "expectedSerial": expected_serial,
            "detectedSerial": detected_serial
        }, merge=True)
        
        return {
            "status": "BLOCKED",
            "alert_id": alert_ref[1].id,
            "reason": "IDENTITY_MISMATCH",
            "location": f"{rack}/{u_pos}",
            "expected_serial": expected_serial,
            "detected_serial": detected_serial
        }
    
    def _check_tier_dependencies(self, device_role: str, device_name: str) -> Dict:
        """Check if device's tier dependencies are satisfied.
        
        Args:
            device_role: Device role (LEAF, SPINE, GPU_NODE, etc.)
            device_name: Device name for alert creation
        
        Returns:
            Dict with 'allowed' boolean and 'reason' string
        """
        # Map device role to tier
        tier_mapping = {
            "LEAF": Tier.BACKEND_FABRIC,
            "SPINE": Tier.BACKEND_FABRIC,
            "CORE": Tier.BACKEND_FABRIC,
            "STORAGE_NODE": Tier.STORAGE,
            "NFS_SERVER": Tier.STORAGE,
            "GPU_NODE": Tier.COMPUTE,
            "COMPUTE_NODE": Tier.COMPUTE
        }
        
        device_tier = tier_mapping.get(device_role)
        
        if not device_tier:
            # Unknown role, allow by default
            return {"allowed": True, "reason": "Unknown role, no tier restrictions"}
        
        # Check dependencies
        dep_check = self.dependency_mgr.check_dependencies(device_tier)
        
        if not dep_check["allowed"]:
            # Create alert
            self.dependency_mgr.create_dependency_block_alert(
                device_name=device_name,
                device_tier=device_tier,
                blocking_tiers=dep_check["blocking_tiers"]
            )
        
        return {
            "allowed": dep_check["allowed"],
            "reason": dep_check["message"],
            "blocking_tiers": dep_check.get("blocking_tiers", [])
        }

    def _handle_cross_su_violation(
        self,
        planned_device: Dict,
        detected_serial: str,
        violation_message: str,
        physical_rack_id: int,
        requested_hostname: str
    ) -> Dict:
        """🚨 CRITICAL ERROR: Switch in wrong Scalable Unit (Multi-SU boundary violation).
        
        Halt IP assignment and create CROSS_SU_CONTAMINATION alert.
        
        This prevents a switch physically located in SU-1 from requesting
        a ZTP configuration meant for SU-2, which would cause:
        - Identity theft (wrong switch personality)
        - Cross-SU traffic hairpinning through Tier 3
        - All-Reduce performance degradation (15-40% slower)
        
        Args:
            planned_device: Device document from Firestore
            detected_serial: Serial number (verified match)
            violation_message: Detailed violation reason from MultiSUValidator
            physical_rack_id: Physical rack where switch is installed
            requested_hostname: Hostname being requested (e.g., "SU2-L3-P0")
            
        Returns:
            Blocked result dict with alert_id and cross-SU details
        """
        device_name = planned_device.get("deviceName")
        location = planned_device.get("location", {})
        rack = location.get("rack", "UNKNOWN")
        u_pos = location.get("uPosition", "UNKNOWN")
        mac_address = planned_device.get("hardwareInfo", {}).get("macAddress")
        
        # Extract SU IDs for reporting
        requested_su = SUIDExtractor.extract_su_id(requested_hostname) if requested_hostname else None
        expected_su = SUIDExtractor.extract_su_id(device_name) if device_name else None
        
        print(f"\n{'🚨 CROSS-SU CONTAMINATION DETECTED'}")
        print(f"   Location: {rack} / {u_pos} (Physical Rack {physical_rack_id})")
        print(f"   Expected Hostname: {device_name} (SU-{expected_su})")
        print(f"   Requested Hostname: {requested_hostname} (SU-{requested_su})")
        print(f"   Serial: {detected_serial} (MATCH - but wrong SU!)")
        print("   ⚠️ ZTP PROVISIONING HALTED")
        print(f"   Violation: {violation_message}")
        
        # Create CRITICAL alert in Firestore
        alert_ref = get_scoped_collection(self.db, self.customer_id, "provisioning_alerts").add({
            "projectId": self.project_id,
            "severity": "CRITICAL",
            "type": "CROSS_SU_CONTAMINATION",
            "status": "UNRESOLVED",
            "location": {
                "rack": rack,
                "uPosition": u_pos,
                "physicalRackId": physical_rack_id
            },
            "planned": {
                "deviceName": device_name,
                "expectedSU": expected_su,
                "serialNumber": detected_serial
            },
            "detected": {
                "requestedHostname": requested_hostname,
                "requestedSU": requested_su,
                "serialNumber": detected_serial,
                "macAddress": mac_address
            },
            "message": f"Multi-SU Boundary Violation: Switch at {rack}/{u_pos} is in SU-{expected_su} but requesting SU-{requested_su} configuration",
            "impact": "ZTP provisioning halted. If allowed, this switch would bridge two isolated Scalable Units, causing All-Reduce traffic to hairpin through Tier 3 with 15-40% performance degradation.",
            "recommendation": "Physical Action Required: Move switch to correct SU or update inventory. DO NOT override - this creates cross-SU fabric contamination.",
            "violationDetails": violation_message,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "resolvedAt": None,
            "resolvedBy": None,
            "resolutionAction": None
        })
        
        # Mark device as BLOCKED in live_infrastructure
        get_scoped_collection(self.db, self.customer_id, "live_infrastructure").document(
            planned_device["firestore_doc_id"]
        ).set({
            "projectId": self.project_id,
            "deviceName": device_name,
            "status": "BLOCKED_CROSS_SU_CONTAMINATION",
            "blockedAt": firestore.SERVER_TIMESTAMP,
            "alertId": alert_ref[1].id,
            "identityVerified": True,  # Serial matches, but wrong SU
            "suBoundaryValidated": False,
            "location": location,
            "expectedSU": expected_su,
            "requestedSU": requested_su,
            "requestedHostname": requested_hostname,
            "detectedSerial": detected_serial
        }, merge=True)
        
        return {
            "status": "BLOCKED",
            "alert_id": alert_ref[1].id,
            "reason": "CROSS_SU_CONTAMINATION",
            "location": f"{rack}/{u_pos}",
            "expected_su": expected_su,
            "requested_su": requested_su,
            "violation_message": violation_message
        }
    
    def _handle_unknown_device(self, mac_address: str) -> Dict:
        """Device with unknown MAC address (not in Day 0 plan).
        
        Could be:
        - Rogue device (security breach)
        - Inventory error (device missing from CSV)
        - Wrong VLAN (device on wrong network segment)
        
        Args:
            mac_address: Unrecognized MAC address
            
        Returns:
            Unknown device result dict
        """
        print("\n❌ UNKNOWN DEVICE")
        print(f"   MAC: {mac_address}")
        print("   Not found in Day 0 schematic extraction")
        
        # Log as MEDIUM severity alert (could be legitimate if inventory incomplete)
        get_scoped_collection(self.db, self.customer_id, "provisioning_alerts").add({
            "projectId": self.project_id,
            "severity": "MEDIUM",
            "type": "UNKNOWN_DEVICE",
            "status": "UNRESOLVED",
            "detected": {
                "macAddress": mac_address
            },
            "message": f"Unknown device with MAC {mac_address} requesting DHCP lease",
            "impact": "Device not in Day 0 plan. Could be rogue device, missing from inventory, or on wrong VLAN.",
            "recommendation": "Check if this device should be added to inventory, verify VLAN configuration, or investigate potential security breach.",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "resolvedAt": None
        })
        
        return {
            "status": "UNKNOWN",
            "mac_address": mac_address
        }
    
    def _handle_unreachable_switch(self, mac_address: str, planned_device: Dict) -> Dict:
        """Switch sent DHCP request but doesn't respond to serial number query.
        
        Possible causes:
        - Switch still booting (boot process not complete)
        - Firmware doesn't support SNMP/SSH yet (needs initial config)
        - Network connectivity issue (cable problem)
        - Wrong credentials (default admin password changed)
        
        Args:
            mac_address: MAC address of unreachable switch
            planned_device: Device document from Firestore
            
        Returns:
            Unreachable result dict
        """
        device_name = planned_device.get("deviceName")
        
        print("\n⚠️ UNREACHABLE SWITCH")
        print(f"   Device: {device_name}")
        print(f"   MAC: {mac_address}")
        print("   Switch booted but not responding to serial query")
        
        get_scoped_collection(self.db, self.customer_id, "provisioning_alerts").add({
            "projectId": self.project_id,
            "severity": "HIGH",
            "type": "UNREACHABLE_SWITCH",
            "status": "UNRESOLVED",
            "planned": {
                "deviceName": device_name
            },
            "detected": {
                "macAddress": mac_address
            },
            "message": f"Switch {device_name} requested DHCP but does not respond to serial query",
            "impact": "Cannot verify identity. IP assignment delayed until switch responds.",
            "recommendation": "Check console access, verify firmware supports SNMP/SSH, confirm default credentials, or wait for boot to complete.",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "resolvedAt": None
        })
        
        return {
            "status": "UNREACHABLE",
            "device_name": device_name,
            "mac_address": mac_address
        }
    
    def _assign_static_ip(self, mac_address: str, ip_address: str, hostname: str, ztp_url: Optional[str] = None):
        """Write DHCP static reservation with optional ZTP script URL.
        
        In production, this would:
        1. Update /etc/dhcp/dhcpd.conf with static host entry
        2. Add DHCP Option 67 (bootfile-name) pointing to ZTP script
        3. Reload DHCP server: systemctl reload isc-dhcp-server
        4. Or call DHCP server API (e.g., Infoblox, Microsoft DHCP, ISC Kea)
        
        Example dhcpd.conf entry with ZTP:
        host IB-SPINE-01 {
            hardware ethernet 00:1B:21:D9:56:E1;
            fixed-address 10.0.1.50;
            option bootfile-name "https://yourapp.com/ztp/IB-SPINE-01.sh";  # Option 67
            option tftp-server-name "yourapp.com";  # Option 66
        }
        
        For development/testing, we log reservations to storage.
        
        Args:
            mac_address: MAC address for static binding
            ip_address: IP to assign
            hostname: Device hostname for dhcpd.conf
            ztp_url: URL for ZTP script download (DHCP Option 67)
        """
        print("📝 Writing static DHCP reservation:")
        print(f"   MAC: {mac_address} → IP: {ip_address} (Host: {hostname})")
        if ztp_url:
            print(f"   ZTP URL (Option 67): {ztp_url}")
        
        # SIMULATION: In production, write to actual DHCP server config
        # For demo, just log to storage
        reservations = db.storage.json.get("dhcp_static_reservations", default=[])
        reservation_entry = {
            "mac": mac_address,
            "ip": ip_address,
            "hostname": hostname,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if ztp_url:
            reservation_entry["ztp_url"] = ztp_url
            reservation_entry["option_67"] = ztp_url  # DHCP Option 67 (bootfile-name)
        
        reservations.append(reservation_entry)
        db.storage.json.put("dhcp_static_reservations", reservations)

    def _parse_vendor_class(self, vendor_class: Optional[str], planned_device: Dict) -> tuple[Optional[str], Optional[str]]:
        """Extract vendor and model from DHCP Option 60 with flexible parsing.
        
        Handles multiple delimiter formats:
        - NVIDIA:QM9700:Onyx (colon)
        - Arista;7060X4;EOS (semicolon)
        - Cisco Systems, Inc.|Nexus 9000 (pipe)
        - Juniper_QFX5200 (underscore)
        - Dell-S5248F-ON (hyphen, vendor extraction only)
        
        Args:
            vendor_class: DHCP Option 60 string
            planned_device: Device doc from Firestore (for fallback)
            
        Returns:
            Tuple of (vendor, model)
            
        Examples:
            >>> _parse_vendor_class("NVIDIA:QM9700", device)
            ("NVIDIA", "QM9700")
            >>> _parse_vendor_class("Arista;7060X4;EOS", device)
            ("Arista", "7060X4")
        """
        import re
        
        vendor = None
        model = None
        
        if vendor_class:
            # Try delimiters in priority order
            for delimiter in [":", ";", "|", "_"]:
                if delimiter in vendor_class:
                    parts = vendor_class.split(delimiter)
                    vendor = parts[0].strip()
                    model = parts[1].strip() if len(parts) > 1 else None
                    print(f"📋 Extracted from DHCP Option 60 (delimiter '{delimiter}'): {vendor} {model}")
                    break
            
            # Fallback: Pattern-based extraction for common vendors
            if not vendor:
                vendor_patterns = {
                    r'^(NVIDIA|Mellanox)': 'NVIDIA',
                    r'^(Arista)': 'Arista',
                    r'^(Cisco)': 'Cisco',
                    r'^(Juniper)': 'Juniper',
                    r'^(Dell)': 'Dell',
                }
                
                for pattern, vendor_name in vendor_patterns.items():
                    if re.match(pattern, vendor_class, re.IGNORECASE):
                        vendor = vendor_name
                        # Try to extract model from rest of string
                        model_match = re.search(r'[-_\s]([A-Z0-9]+[-_]?[A-Z0-9]*)', vendor_class)
                        if model_match:
                            model = model_match.group(1)
                        print(f"📋 Extracted via pattern match: {vendor} {model}")
                        break
        
        # Fallback to planned device hardware info
        if not vendor or not model:
            hw_info = planned_device.get("hardwareInfo", {})
            vendor = vendor or hw_info.get("vendor")
            model = model or hw_info.get("model")
            if vendor and model:
                print(f"📋 Using planned hardware info: {vendor} {model}")
        
        return vendor, model


def resolve_identity_mismatch(
    alert_id: str,
    resolution_action: str,
    resolved_by: str,
    customer_id: str
) -> Dict:
    """Installation Lead resolves an identity mismatch alert.
    
    Three resolution strategies:
    
    1. SWAP_HARDWARE: Technician will physically move the switch to correct rack.
       Use when: Hardware was racked in wrong location.
       Result: Alert marked resolved, waiting for physical correction.
    
    2. UPDATE_INVENTORY: Accept detected hardware as correct, update Firestore.
       Use when: Day 0 inventory was wrong, but physical reality is correct.
       Result: Firestore updated with actual serial, device unblocked.
    
    3. OVERRIDE_AND_PROCEED: Proceed despite mismatch (DANGEROUS).
       Use when: Installation Lead accepts the risk and wants to proceed.
       Result: Device unblocked, but configuration may not match hardware.
       ⚠️ WARNING: Can lead to catastrophic configuration errors.
    
    Args:
        alert_id: Firestore document ID of the alert
        resolution_action: "SWAP_HARDWARE" | "UPDATE_INVENTORY" | "OVERRIDE_AND_PROCEED"
        resolved_by: User ID/email of the Installation Lead
        customer_id: Customer ID for data isolation
        
    Returns:
        Result dict with status and message
        
    Raises:
        ValueError: If alert_id not found or resolution_action invalid
    """
    # Initialize Firestore
    credentials_json = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
    if credentials_json:
        import json
        from google.oauth2 import service_account
        credentials_dict = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        firestore_client = firestore.Client(credentials=credentials)
    else:
        firestore_client = firestore.Client()
        
    from app.libs.audit_logger import AuditLogger
    audit_logger = AuditLogger(firestore_client)
    
    # Get alert details (customer-scoped)
    alert_ref = get_scoped_collection(firestore_client, customer_id, "provisioning_alerts").document(alert_id)
    alert_doc = alert_ref.get()
    
    if not alert_doc.exists:
        raise ValueError(f"Alert {alert_id} not found")
    
    alert = alert_doc.to_dict()
    
    if resolution_action == "SWAP_HARDWARE":
        # Lead will physically move the switch to correct rack
        alert_ref.update({
            "status": "RESOLVED",
            "resolution": "Hardware will be physically moved to correct location",
            "resolutionAction": "SWAP_HARDWARE",
            "resolvedBy": resolved_by,
            "resolvedAt": firestore.SERVER_TIMESTAMP
        })
        
        audit_logger.log_action(
            user_email=resolved_by,
            customer_id=customer_id,
            action="resolved_alert_swap_hardware",
            details={
                "alert_id": alert_id,
                "planned_device": alert["planned"]["deviceName"],
                "detected_serial": alert["detected"]["serialNumber"]
            },
            project_id=alert["projectId"]
        )
        
        return {
            "status": "PENDING_PHYSICAL_SWAP",
            "message": "Alert marked resolved. Waiting for technician to move hardware to correct rack location."
        }
    
    elif resolution_action == "UPDATE_INVENTORY":
        # Reality matches hardware, update Firestore to reflect actual state
        detected_serial = alert["detected"]["serialNumber"]
        planned_device_name = alert["planned"]["deviceName"]
        project_id = alert["projectId"]
        
        # Update the device record with actual serial (customer-scoped)
        devices_query = get_scoped_collection(firestore_client, customer_id, "extracted_devices").where(
            "projectId", "==", project_id
        ).where(
            "deviceName", "==", planned_device_name
        ).limit(1).stream()
        
        for doc in devices_query:
            doc.reference.update({
                "hardwareInfo.serialNumber": detected_serial,
                "inventoryUpdated": True,
                "inventoryUpdateReason": "Matched to physical hardware during Day 1 provisioning",
                "updatedBy": resolved_by,
                "updatedAt": firestore.SERVER_TIMESTAMP
            })
            
            # Unblock the device in live_infrastructure (customer-scoped)
            live_ref = get_scoped_collection(firestore_client, customer_id, "live_infrastructure").document(doc.id)
            live_ref.update({
                "status": "INVENTORY_UPDATED",
                "identityVerified": True,
                "serialNumberMatch": "UPDATED",
                "updatedSerial": detected_serial
            })
        
        alert_ref.update({
            "status": "RESOLVED",
            "resolution": f"Inventory updated to match physical hardware (Serial: {detected_serial})",
            "resolutionAction": "UPDATE_INVENTORY",
            "resolvedBy": resolved_by,
            "resolvedAt": firestore.SERVER_TIMESTAMP
        })
        
        audit_logger.log_action(
            user_email=resolved_by,
            customer_id=customer_id,
            action="resolved_alert_update_inventory",
            details={
                "alert_id": alert_id,
                "planned_device": planned_device_name,
                "old_serial": alert["planned"]["serialNumber"],
                "new_serial": detected_serial
            },
            project_id=project_id
        )
        
        return {
            "status": "INVENTORY_UPDATED",
            "message": f"Inventory updated with actual serial {detected_serial}. Device unblocked and ready for configuration."
        }
    
    elif resolution_action == "OVERRIDE_AND_PROCEED":
        # Lead acknowledges mismatch but wants to proceed anyway (use with caution)
        detected_serial = alert["detected"]["serialNumber"]
        
        alert_ref.update({
            "status": "RESOLVED",
            "resolution": "Installation Lead override - proceeding with detected hardware despite mismatch",
            "resolutionAction": "OVERRIDE_AND_PROCEED",
            "resolvedBy": resolved_by,
            "resolvedAt": firestore.SERVER_TIMESTAMP,
            "overrideWarning": "⚠️ Manual override applied - configuration may not match hardware. Proceed with caution."
        })
        
        planned_device_name = alert["planned"]["deviceName"]
        project_id = alert["projectId"]
        
        audit_logger.log_action(
            user_email=resolved_by,
            customer_id=customer_id,
            action="resolved_alert_override",
            details={
                "alert_id": alert_id,
                "planned_device": planned_device_name,
                "expected_serial": alert["planned"]["serialNumber"],
                "detected_serial": detected_serial,
                "warning": "MANUAL OVERRIDE APPLIED"
            },
            project_id=project_id
        )
        
        # Unblock device with warning flag
        planned_device_name = alert["planned"]["deviceName"]
        project_id = alert["projectId"]
        
        devices_query = get_scoped_collection(firestore_client, customer_id, "extracted_devices").where(
            "projectId", "==", project_id
        ).where(
            "deviceName", "==", planned_device_name
        ).limit(1).stream()
        
        for doc in devices_query:
            live_ref = get_scoped_collection(firestore_client, customer_id, "live_infrastructure").document(doc.id)
            live_ref.update({
                "status": "OVERRIDE_APPLIED",
                "identityVerified": False,
                "serialNumberMatch": "OVERRIDE",
                "overrideAppliedBy": resolved_by,
                "overrideWarning": "Configuration may not match actual hardware"
            })
        
        return {
            "status": "OVERRIDE_APPLIED",
            "message": "⚠️ Override applied. Device unblocked. ENSURE configuration matches actual hardware before pushing config."
        }
    
    else:
        raise ValueError(f"Unknown resolution action: {resolution_action}")
