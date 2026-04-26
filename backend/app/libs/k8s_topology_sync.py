"""K8sTopologySync - Bridge Firestore Infrastructure to Kubernetes Labels

This is the CRITICAL MISSING LINK that makes Kubernetes topology-aware.
Without it, K8s treats a multi-SU SuperPOD fabric as a flat resource pool,
causing catastrophic performance degradation.

**Problem Solved:**
Your Firestore `live_infrastructure` collection contains the physical truth:
- Which node is in which SU (Scalable Unit)
- Which rack each node is in
- Which rail/plane (InfiniBand tail) each node is connected to

But Kubernetes has NO KNOWLEDGE of this topology. The scheduler will happily:
- Place a 128-GPU job across 4 different SUs (10x latency)
- Break NVLink by spanning racks
- Misalign RDMA NICs (GPU 0 talking on Tail 1 instead of Tail 0)

**Solution:**
This service queries Firestore and applies standard Kubernetes labels:
- `ai.factory/su-id`: Prevents cross-SU placement
- `ai.factory/rack-id`: Enables rack-local scheduling
- `ai.factory/rail-id`: Aligns RDMA NICs with GPU topology
- `topology.kubernetes.io/zone`: Standard K8s zone label
- `ai.factory/roce-ready`: Only set after LLDP validation

**Usage:**
    from app.libs.k8s_topology_sync import K8sTopologySync
    
    sync = K8sTopologySync(project_id="my-cluster", db_client=firestore_client)
    result = sync.sync_all_nodes()
    
    print(f"Synced {result['synced_count']} nodes")

**Integration Points:**
1. Called automatically after K8s worker join (k8s_provisioner.py)
2. Called after LLDP validation completes (wiring_validator.py)
3. Called periodically via cron (every 5 minutes)
4. Called manually via API endpoint for troubleshooting
"""

import subprocess
import json
from typing import Dict, Optional
from google.cloud import firestore
from app.libs.multi_su_test_suite import SUIDExtractor


class K8sTopologySync:
    """Synchronizes Firestore infrastructure topology to Kubernetes node labels.
    
    This class implements the "Physical Truth → Logical Labels" translation
    that enables CoreWeave-style topology-aware scheduling without NVIDIA BCM.
    
    **Label Schema:**
    - `ai.factory/su-id`: Scalable Unit ID (1-N)
    - `ai.factory/rack-id`: Rack ID within SU (1-8 for standard 8-rack SU)
    - `ai.factory/rail-id`: InfiniBand rail/plane (0 or 1 for dual-rail)
    - `ai.factory/roce-ready`: "true" only if LLDP validation passed
    - `topology.kubernetes.io/zone`: "SU{su_id}-Rack{rack_id}" (K8s standard)
    - `topology.kubernetes.io/region`: "SU{su_id}" (K8s standard)
    
    **Why These Labels Matter:**
    
    1. **SU Isolation:** A 128-GPU training job must stay within one SU.
       Cross-SU traffic hits the Tier-3 bottleneck (8x200G vs 128x400G).
       
    2. **Rack Locality:** NVLink only works within a rack. Placing GPUs
       across racks breaks GPU-Direct and forces traffic through switches.
       
    3. **Rail Alignment:** Each GPU has 2 NICs (Tail 0, Tail 1). If GPU 0
       sends on Tail 0 but GPU 1 receives on Tail 1, NCCL performance drops 50%.
       
    4. **RoCE Readiness:** Don't schedule GPU jobs on nodes with mis-wired
       fabric. The roce-ready label is only set after LLDP confirms correct cabling.
    
    Attributes:
        project_id: Firestore project ID to query
        db: Firestore client instance
    """
    
    def __init__(self, project_id: str, db_client: firestore.Client):
        """Initialize topology sync service.
        
        Args:
            project_id: Firestore project ID
            db_client: Initialized Firestore client
        """
        self.project_id = project_id
        self.db = db_client
        print(f"🔗 K8sTopologySync initialized for project {project_id}")
    
    def sync_all_nodes(self) -> Dict:
        """Query Firestore for all COMPUTE nodes and sync labels to K8s.
        
        This is the main entry point. It:
        1. Queries Firestore for all verified compute nodes
        2. Extracts topology metadata (SU, Rack, Rail)
        3. Applies labels to corresponding K8s nodes
        4. Returns summary statistics
        
        Returns:
            Dict with keys:
            - synced_count: Number of nodes successfully labeled
            - failed_count: Number of nodes that failed
            - total_nodes: Total nodes found in Firestore
            - errors: List of error messages
            - synced_nodes: List of successfully synced node names
            
        Example:
            >>> result = sync.sync_all_nodes()
            >>> print(f"Synced {result['synced_count']}/{result['total_nodes']} nodes")
            Synced 128/128 nodes
        """
        print(f"\n{'='*70}")
        print(f"🔄 Starting Topology Sync for project {self.project_id}")
        print(f"{'='*70}")
        
        # Step 1: Query Firestore for all verified compute nodes
        nodes_ref = self.db.collection("live_infrastructure")
        query = (
            nodes_ref
            .where("projectId", "==", self.project_id)
            .where("tier", "==", "COMPUTE")
            .where("status", "in", ["OPERATIONAL", "CONFIGURING", "DISCOVERY_VERIFIED"])
        )
        
        nodes = list(query.stream())
        synced_count = 0
        failed_count = 0
        errors = []
        synced_nodes = []
        
        print(f"📊 Found {len(nodes)} compute nodes in Firestore")
        
        if len(nodes) == 0:
            print("⚠️ No compute nodes found. Have nodes completed ZTP and joined K8s?")
            return {
                "synced_count": 0,
                "failed_count": 0,
                "total_nodes": 0,
                "errors": ["No compute nodes found in Firestore"],
                "synced_nodes": []
            }
        
        for node_doc in nodes:
            node_data = node_doc.to_dict()
            
            try:
                # Step 2: Extract topology data from Firestore document
                hostname = node_data.get("hostname", node_data.get("deviceName", ""))
                
                if not hostname:
                    errors.append("Node document missing hostname/deviceName field")
                    failed_count += 1
                    continue
                
                # Extract SU ID from hostname (e.g., "DGX-SU1-R02-S05" → SU_ID=1)
                su_id = self._extract_su_id(hostname, node_data)
                
                # Extract rack ID from location metadata
                location = node_data.get("location", {})
                rack_id = location.get("rack") or location.get("rackId")
                
                # Extract rail/plane ID from network metadata
                network_metadata = node_data.get("networkMetadata", {})
                rail_id = network_metadata.get("planeId") or network_metadata.get("plane_id")
                
                # Get management IP for debugging
                mgmt_ip = node_data.get("mgmtIp") or node_data.get("assignedIp")
                
                # Validate we have required data
                if su_id is None:
                    errors.append(f"Could not extract SU ID from hostname: {hostname}")
                    failed_count += 1
                    continue
                
                if rack_id is None:
                    errors.append(f"Missing rack ID for {hostname}")
                    failed_count += 1
                    continue
                
                if rail_id is None:
                    # Default to rail 0 if not specified (for single-rail clusters)
                    rail_id = 0
                    print(f"  ⚠️ {hostname}: No rail ID found, defaulting to 0")
                
                # Step 3: Build label map
                labels = {
                    "ai.factory/su-id": str(su_id),
                    "ai.factory/rack-id": str(rack_id),
                    "ai.factory/rail-id": str(rail_id),
                    "topology.kubernetes.io/zone": f"SU{su_id}-Rack{rack_id}",
                    "topology.kubernetes.io/region": f"SU{su_id}",
                }
                
                # Step 4: Check if RoCE fabric is validated via LLDP
                lldp_validated = node_data.get("lldpValidated", False)
                if lldp_validated:
                    labels["ai.factory/roce-ready"] = "true"
                    print(f"  🟢 {hostname}: RoCE fabric validated")
                else:
                    labels["ai.factory/roce-ready"] = "false"
                    print(f"  🟡 {hostname}: RoCE fabric NOT validated (LLDP pending)")
                
                # Step 5: Apply labels to K8s node
                # Node name in K8s might be different from hostname
                # Try hostname first, then try with lowercase, then try mgmt_ip
                k8s_node_name = self._find_k8s_node_name(hostname, mgmt_ip)
                
                if not k8s_node_name:
                    errors.append(f"Node {hostname} not found in K8s cluster")
                    failed_count += 1
                    print(f"  ❌ {hostname}: Not found in K8s cluster")
                    continue
                
                self._apply_labels_to_node(k8s_node_name, labels)
                
                synced_count += 1
                synced_nodes.append(k8s_node_name)
                print(f"  ✅ {hostname} → {k8s_node_name} (SU{su_id}, Rack{rack_id}, Rail{rail_id})")
                
            except Exception as e:
                failed_count += 1
                error_msg = f"Failed {hostname if 'hostname' in locals() else 'unknown'}: {str(e)}"
                errors.append(error_msg)
                print(f"  ❌ {error_msg}")
        
        print(f"\n{'='*70}")
        print(f"📈 Sync Complete: {synced_count} synced, {failed_count} failed")
        print(f"{'='*70}\n")
        
        return {
            "synced_count": synced_count,
            "failed_count": failed_count,
            "total_nodes": len(nodes),
            "errors": errors,
            "synced_nodes": synced_nodes
        }
    
    def _extract_su_id(self, hostname: str, node_data: Dict) -> Optional[int]:
        """Extract SU ID from hostname or metadata.
        
        Tries multiple strategies:
        1. Use SUIDExtractor on hostname (e.g., "SU1-L3-P0" → 1)
        2. Check networkMetadata.suId field
        3. Check location.suId field
        4. Parse hostname for patterns like "DGX-SU1-..." → 1
        
        Args:
            hostname: Node hostname
            node_data: Full Firestore document
            
        Returns:
            SU ID as integer, or None if not found
        """
        # Strategy 1: Use SUIDExtractor (for switch-style hostnames)
        su_id = SUIDExtractor.extract_su_id(hostname)
        if su_id is not None:
            return su_id
        
        # Strategy 2: Check metadata fields
        network_metadata = node_data.get("networkMetadata", {})
        if "suId" in network_metadata:
            return int(network_metadata["suId"])
        
        location = node_data.get("location", {})
        if "suId" in location:
            return int(location["suId"])
        
        # Strategy 3: Parse hostname for "SU{N}" pattern
        import re
        match = re.search(r'SU(\d+)', hostname, re.IGNORECASE)
        if match:
            return int(match.group(1))
        
        # Strategy 4: Default to SU 1 for single-SU clusters
        # (This is safe for MVP but should be configurable)
        print(f"  ⚠️ Could not extract SU ID from {hostname}, defaulting to SU 1")
        return 1
    
    def _find_k8s_node_name(self, hostname: str, mgmt_ip: Optional[str] = None) -> Optional[str]:
        """Find the actual K8s node name corresponding to a hostname.
        
        K8s node names might not match Firestore hostnames exactly.
        This tries multiple strategies to find the correct node.
        
        Args:
            hostname: Hostname from Firestore
            mgmt_ip: Management IP from Firestore (optional)
            
        Returns:
            K8s node name if found, None otherwise
        """
        # Get all K8s nodes
        try:
            cmd = ["kubectl", "get", "nodes", "-o", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            nodes_data = json.loads(result.stdout)
            
            # Build a list of (node_name, internal_ip, hostname)
            k8s_nodes = []
            for node in nodes_data.get("items", []):
                node_name = node["metadata"]["name"]
                
                # Get internal IP
                internal_ip = None
                for addr in node["status"].get("addresses", []):
                    if addr["type"] == "InternalIP":
                        internal_ip = addr["address"]
                        break
                
                # Get hostname label
                k8s_hostname = node["metadata"].get("labels", {}).get("kubernetes.io/hostname", node_name)
                
                k8s_nodes.append({
                    "name": node_name,
                    "internal_ip": internal_ip,
                    "hostname": k8s_hostname
                })
            
            # Strategy 1: Exact match on node name
            for node in k8s_nodes:
                if node["name"] == hostname:
                    return node["name"]
            
            # Strategy 2: Case-insensitive match
            for node in k8s_nodes:
                if node["name"].lower() == hostname.lower():
                    return node["name"]
            
            # Strategy 3: Match on hostname label
            for node in k8s_nodes:
                if node["hostname"].lower() == hostname.lower():
                    return node["name"]
            
            # Strategy 4: Match on internal IP (if provided)
            if mgmt_ip:
                for node in k8s_nodes:
                    if node["internal_ip"] == mgmt_ip:
                        return node["name"]
            
            # Strategy 5: Partial match (e.g., "DGX-SU1-R02-S05" matches "dgx-su1-r02-s05")
            hostname_normalized = hostname.lower().replace("_", "-")
            for node in k8s_nodes:
                node_normalized = node["name"].lower().replace("_", "-")
                if hostname_normalized in node_normalized or node_normalized in hostname_normalized:
                    return node["name"]
            
            return None
            
        except Exception as e:
            print(f"  ⚠️ Error querying K8s nodes: {e}")
            return None
    
    def _apply_labels_to_node(self, node_name: str, labels: Dict[str, str]):
        """Apply labels to a K8s node using kubectl.
        
        Args:
            node_name: Kubernetes node name
            labels: Dict of label key-value pairs
            
        Raises:
            RuntimeError: If kubectl command fails
        """
        # Build kubectl command
        # Format: kubectl label node <name> key1=value1 key2=value2 --overwrite
        label_args = []
        for key, value in labels.items():
            label_args.append(f"{key}={value}")
        
        cmd = ["kubectl", "label", "node", node_name] + label_args + ["--overwrite"]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"kubectl label failed: {result.stderr}")
    
    def get_node_topology(self, node_name: str) -> Dict:
        """Get topology labels for a specific node.
        
        Useful for debugging and validation.
        
        Args:
            node_name: Kubernetes node name
            
        Returns:
            Dict with su_id, rack_id, rail_id, roce_ready, zone, region
            
        Raises:
            RuntimeError: If node not found or kubectl fails
            
        Example:
            >>> topology = sync.get_node_topology("dgx-su1-r02-s05")
            >>> print(topology)
            {'su_id': '1', 'rack_id': '2', 'rail_id': '0', 'roce_ready': True, ...}
        """
        cmd = [
            "kubectl", "get", "node", node_name,
            "-o", "jsonpath={.metadata.labels}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Node {node_name} not found: {result.stderr}")
        
        # Parse labels (output is JSON string)
        labels = json.loads(result.stdout)
        
        return {
            "su_id": labels.get("ai.factory/su-id"),
            "rack_id": labels.get("ai.factory/rack-id"),
            "rail_id": labels.get("ai.factory/rail-id"),
            "roce_ready": labels.get("ai.factory/roce-ready") == "true",
            "zone": labels.get("topology.kubernetes.io/zone"),
            "region": labels.get("topology.kubernetes.io/region"),
        }
    
    def verify_all_nodes_labeled(self) -> Dict:
        """Verify that all K8s nodes have topology labels.
        
        This is a health check to ensure sync is working correctly.
        
        Returns:
            Dict with:
            - total_nodes: Total nodes in K8s
            - labeled_nodes: Nodes with ai.factory/su-id label
            - unlabeled_nodes: Nodes missing topology labels
            - unlabeled_node_names: List of unlabeled node names
        """
        cmd = ["kubectl", "get", "nodes", "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        nodes_data = json.loads(result.stdout)
        
        total_nodes = len(nodes_data.get("items", []))
        labeled_count = 0
        unlabeled_names = []
        
        for node in nodes_data.get("items", []):
            node_name = node["metadata"]["name"]
            labels = node["metadata"].get("labels", {})
            
            if "ai.factory/su-id" in labels:
                labeled_count += 1
            else:
                unlabeled_names.append(node_name)
        
        return {
            "total_nodes": total_nodes,
            "labeled_nodes": labeled_count,
            "unlabeled_nodes": total_nodes - labeled_count,
            "unlabeled_node_names": unlabeled_names
        }
