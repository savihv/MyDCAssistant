"""Kubernetes Cluster Management API

✅ Subprocess-based implementation using kubectl commands

Provides REST endpoints for K8s cluster management during GPU cloud bootstrap.
Uses system `kubectl` binary - no Python SDK dependencies.

**Endpoints:**
- POST /kubernetes/bootstrap - Deploy control plane
- POST /kubernetes/join-node - Add worker to cluster
- GET /kubernetes/nodes - List all nodes with GPU inventory
- GET /kubernetes/cluster-status - Cluster health metrics
- GET /kubernetes/node/{name} - Detailed node info

**Integration with ZTP:**
DHCPScraper calls /join-node after OS provisioning completes.
"""

import json
import subprocess
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.libs.k8s_provisioner import K8sProvisioner

router = APIRouter(prefix="/kubernetes")

# Initialize provisioner
provisioner = K8sProvisioner()


# === Request/Response Models ===

class BootstrapRequest(BaseModel):
    """Request to bootstrap K3s control plane."""
    control_plane_ip: str  # Admin node IP to become control plane


class BootstrapResponse(BaseModel):
    """Control plane deployment result."""
    status: str  # SUCCESS, FAILED
    control_plane_ip: str
    kubeconfig: Optional[str] = None
    error: Optional[str] = None


class JoinNodeRequest(BaseModel):
    """Request to join worker node to cluster."""
    node_ip: str  # Management IP from DHCP
    node_hostname: str  # e.g., SU1-RACK01-SRV01
    tier: str = "COMPUTE"  # COMPUTE, STORAGE, ADMIN
    gpu_count: int = 8  # Expected GPU count (for validation)


class JoinNodeResponse(BaseModel):
    """Worker node join result."""
    status: str  # SUCCESS, FAILED, SKIPPED, TIMEOUT
    node_hostname: str
    node_ip: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class NodeInfo(BaseModel):
    """K8s node details with GPU info."""
    name: str
    status: str  # Ready, NotReady, Unknown
    ip: str
    tier: str
    gpu_count: int
    cpu_cores: int
    memory_gb: int
    created_at: str
    provisioned_by: str  # dhcp-scraper, manual, etc.


class ClusterStatus(BaseModel):
    """Cluster health metrics."""
    total_nodes: int
    ready_nodes: int
    total_gpus: int
    control_plane_ip: str


# === Helper Functions ===

def run_kubectl(args: list, timeout: int = 30) -> dict:
    """Execute kubectl command and return JSON output.
    
    Args:
        args: kubectl arguments (e.g., ["get", "nodes"])
        timeout: Command timeout in seconds
        
    Returns:
        Parsed JSON output from kubectl
        
    Raises:
        HTTPException if kubectl fails
    """
    cmd = ["kubectl"] + args + ["-o", "json"]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True
        )
        return json.loads(result.stdout)
        
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"kubectl command failed: {e.stderr}"
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=408,
            detail=f"kubectl command timed out after {timeout}s"
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse kubectl JSON output: {e}"
        )


def parse_node_info(node_data: dict) -> NodeInfo:
    """Parse kubectl node JSON into NodeInfo model.
    
    Args:
        node_data: Node object from kubectl get node -o json
        
    Returns:
        Structured NodeInfo object
    """
    metadata = node_data.get("metadata", {})
    status_data = node_data.get("status", {})
    labels = metadata.get("labels", {})
    allocatable = status_data.get("allocatable", {})
    
    # Determine node status
    node_status = "Unknown"
    conditions = status_data.get("conditions", [])
    for condition in conditions:
        if condition.get("type") == "Ready":
            node_status = "Ready" if condition.get("status") == "True" else "NotReady"
            break
    
    # Get node IP
    node_ip = "unknown"
    addresses = status_data.get("addresses", [])
    for addr in addresses:
        if addr.get("type") == "InternalIP":
            node_ip = addr.get("address", "unknown")
            break
    
    # Parse resources
    gpu_count = int(allocatable.get("nvidia.com/gpu", "0"))
    cpu_cores = int(allocatable.get("cpu", "0").replace("m", "")) // 1000 if "m" in allocatable.get("cpu", "0") else int(allocatable.get("cpu", "0"))
    memory_str = allocatable.get("memory", "0Ki")
    memory_gb = int(memory_str.replace("Ki", "")) // (1024 * 1024) if "Ki" in memory_str else 0
    
    return NodeInfo(
        name=metadata.get("name", "unknown"),
        status=node_status,
        ip=node_ip,
        tier=labels.get("topology.ai-factory/tier", "unknown"),
        gpu_count=gpu_count,
        cpu_cores=cpu_cores,
        memory_gb=memory_gb,
        created_at=metadata.get("creationTimestamp", "unknown"),
        provisioned_by=labels.get("topology.ai-factory/provisioned-by", "manual")
    )


# === API Endpoints ===

@router.post("/bootstrap", response_model=BootstrapResponse)
async def bootstrap_control_plane_endpoint(request: BootstrapRequest):
    """Deploy K3s control plane on admin node.
    
    This is a ONE-TIME operation to initialize the cluster.
    Subsequent nodes join via /join-node.
    
    **Usage:**
    ```
    POST /kubernetes/bootstrap
    {
        "control_plane_ip": "10.0.0.10"
    }
    ```
    """
    result = provisioner.bootstrap_control_plane(request.control_plane_ip)
    
    return BootstrapResponse(
        status=result["status"],
        control_plane_ip=result.get("control_plane_ip", request.control_plane_ip),
        kubeconfig=result.get("cluster_info"),
        error=result.get("error")
    )


@router.post("/join-node", response_model=JoinNodeResponse)
async def join_worker_node(request: JoinNodeRequest):
    """Add worker node to K8s cluster after ZTP provisioning.
    
    Called by DHCPScraper after OS installation completes.
    Only COMPUTE tier nodes join the cluster.
    
    **Usage:**
    ```
    POST /kubernetes/join-node
    {
        "node_ip": "10.244.1.5",
        "node_hostname": "SU1-RACK01-SRV01",
        "tier": "COMPUTE",
        "gpu_count": 8
    }
    ```
    """
    result = await provisioner.join_worker_node(
        node_ip=request.node_ip,
        node_hostname=request.node_hostname,
        tier=request.tier,
        gpu_count=request.gpu_count
    )
    
    return JoinNodeResponse(
        status=result["status"],
        node_hostname=result.get("node_hostname", request.node_hostname),
        node_ip=result.get("node_ip"),
        message=result.get("message"),
        error=result.get("error")
    )


@router.get("/nodes", response_model=list[NodeInfo])
async def list_cluster_nodes():
    """List all K8s nodes with GPU inventory.
    
    Returns detailed info for each node including:
    - GPU count (from nvidia.com/gpu resource)
    - Node status (Ready/NotReady)
    - Tier label (COMPUTE/STORAGE/ADMIN)
    - Provisioning source (dhcp-scraper, manual, etc.)
    
    **Usage:**
    ```
    GET /kubernetes/nodes
    ```
    """
    try:
        nodes_data = run_kubectl(["get", "nodes"])
        items = nodes_data.get("items", [])
        
        return [parse_node_info(node) for node in items]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list nodes: {str(e)}"
        )


@router.get("/cluster-status", response_model=ClusterStatus)
async def get_cluster_status():
    """Get cluster health metrics.
    
    Returns:
    - Total/Ready node counts
    - Total GPU count across cluster
    - Control plane IP
    
    **Usage:**
    ```
    GET /kubernetes/cluster-status
    ```
    """
    result = await provisioner.get_cluster_status()
    
    if "error" in result:
        raise HTTPException(
            status_code=500,
            detail=result["error"]
        )
    
    return ClusterStatus(**result)


@router.get("/node/{node_name}", response_model=NodeInfo)
async def get_node_details(node_name: str):
    """Get detailed info for a specific node.
    
    Args:
        node_name: K8s node name (e.g., SU1-RACK01-SRV01)
    
    **Usage:**
    ```
    GET /kubernetes/node/SU1-RACK01-SRV01
    ```
    """
    try:
        node_data = run_kubectl(["get", "node", node_name])
        return parse_node_info(node_data)
        
    except HTTPException:
        raise HTTPException(
            status_code=404,
            detail=f"Node {node_name} not found in cluster"
        )


class ZTPCompletionRequest(BaseModel):
    """ZTP completion webhook payload."""
    node_hostname: str  # e.g., SU1-RACK01-SRV01
    node_ip: str  # Management IP
    mac_address: str  # For Firestore lookup
    ztp_status: str  # SUCCESS, FAILED
    error: Optional[str] = None


class ZTPCompletionResponse(BaseModel):
    """ZTP completion webhook response."""
    status: str  # ACCEPTED, K8S_JOIN_TRIGGERED, SKIPPED, ERROR
    message: str
    k8s_join_status: Optional[str] = None


@router.post("/ztp-complete", response_model=ZTPCompletionResponse)
async def handle_ztp_completion(request: ZTPCompletionRequest):
    """Handle ZTP completion webhook and trigger K8s worker join.
    
    Called by switches/nodes after ZTP script execution completes.
    For COMPUTE tier nodes, this triggers automatic K8s cluster join.
    
    **Workflow:**
    1. ZTP script completes OS installation
    2. Node sends POST /kubernetes/ztp-complete
    3. Lookup node in Firestore (check k8s_join_pending flag)
    4. If COMPUTE node → trigger K8s join via K8sProvisioner
    5. Return status
    
    **Usage:**
    ```
    POST /kubernetes/ztp-complete
    {
        "node_hostname": "SU1-RACK01-SRV01",
        "node_ip": "10.244.1.5",
        "mac_address": "00:1A:2B:3C:4D:5E",
        "ztp_status": "SUCCESS"
    }
    ```
    """
    import os
    import json
    from google.cloud import firestore
    from google.oauth2 import service_account
    
    print(f"\n{'='*70}")
    print(f"✅ ZTP COMPLETION WEBHOOK: {request.node_hostname}")
    print(f"   IP: {request.node_ip}")
    print(f"   MAC: {request.mac_address}")
    print(f"   Status: {request.ztp_status}")
    print(f"{'='*70}")
    
    # Check ZTP status
    if request.ztp_status != "SUCCESS":
        return ZTPCompletionResponse(
            status="SKIPPED",
            message=f"ZTP failed, K8s join skipped. Error: {request.error}"
        )
    
    # Initialize Firestore
    try:
        creds = service_account.Credentials.from_service_account_info(
            json.loads(os.environ.get("FIREBASE_ADMIN_CREDENTIALS"))
        )
        db = firestore.Client(credentials=creds)
        
        # Lookup node in Firestore by MAC address
        mac_normalized = request.mac_address.upper().replace("-", ":").replace(".", ":")
        
        query = db.collection("live_infrastructure").where(
            "macAddress", "==", mac_normalized
        ).limit(1)
        
        results = list(query.stream())
        
        if not results:
            return ZTPCompletionResponse(
                status="ERROR",
                message=f"Node {request.node_hostname} not found in Firestore"
            )
        
        node_doc = results[0]
        node_data = node_doc.to_dict()
        
        # Check if K8s join is pending
        if not node_data.get("k8s_join_pending", False):
            return ZTPCompletionResponse(
                status="SKIPPED",
                message=f"Node {request.node_hostname} is not a COMPUTE node, K8s join not needed"
            )
        
        # Trigger K8s join
        print("\n🔗 COMPUTE NODE READY: Triggering K8s auto-join")
        
        gpu_count = node_data.get("k8s_expected_gpus", 8)
        
        join_result = await provisioner.join_worker_node(
            node_ip=request.node_ip,
            node_hostname=request.node_hostname,
            tier="COMPUTE",
            gpu_count=gpu_count
        )
        
        # Update Firestore with K8s join status
        node_doc.reference.update({
            "k8s_join_status": join_result["status"],
            "k8s_join_at": firestore.SERVER_TIMESTAMP,
            "k8s_join_pending": False
        })
        
        if join_result["status"] == "SUCCESS":
            print(f"✅ K8s join successful: {request.node_hostname}")
            return ZTPCompletionResponse(
                status="K8S_JOIN_TRIGGERED",
                message=f"Node {request.node_hostname} successfully joined K8s cluster",
                k8s_join_status="SUCCESS"
            )
        elif join_result["status"] == "TIMEOUT":
            print(f"⏳ K8s join timeout: {request.node_hostname}")
            return ZTPCompletionResponse(
                status="K8S_JOIN_TRIGGERED",
                message=join_result.get("message", "K8s join timed out but may complete later"),
                k8s_join_status="TIMEOUT"
            )
        else:
            print(f"❌ K8s join failed: {request.node_hostname}")
            return ZTPCompletionResponse(
                status="ERROR",
                message=join_result.get("error", "K8s join failed"),
                k8s_join_status="FAILED"
            )
    
    except Exception as e:
        print(f"❌ Error handling ZTP completion: {e}")
        return ZTPCompletionResponse(
            status="ERROR",
            message=f"Internal error: {str(e)}"
        )
