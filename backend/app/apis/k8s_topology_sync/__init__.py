"""K8sTopologySync API Endpoints

Provides HTTP API for triggering topology synchronization between Firestore
and Kubernetes node labels.

**Endpoints:**

1. POST /sync-topology/{project_id}
   - Trigger full topology sync for all nodes in project
   - Called automatically after K8s joins, LLDP validation
   - Can be called manually for troubleshooting
   
2. GET /node-topology/{node_name}
   - Get topology labels for a specific node
   - Useful for debugging and validation
   
3. GET /verify-sync/{project_id}
   - Health check: verify all nodes have topology labels
   - Returns count of labeled vs unlabeled nodes
   
4. POST /sync-single-node/{node_name}
   - Sync topology for a single node (faster than full sync)
   - Useful after node replacement or hardware changes

**Integration Points:**
- Called by k8s_provisioner.py after worker join
- Called by wiring_validator.py after LLDP validation
- Called by cron job every 5 minutes
- Called manually via UI for troubleshooting
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional
from app.libs.k8s_topology_sync import K8sTopologySync
from google.cloud import firestore
import os
import json

router = APIRouter()

# Initialize Firestore client
try:
    firebase_creds = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
    if firebase_creds:
        creds = json.loads(firebase_creds)
        db = firestore.Client.from_service_account_info(creds)
    else:
        # Fallback for local development
        db = firestore.Client()
except Exception as e:
    print(f"⚠️ Warning: Could not initialize Firestore client: {e}")
    db = None


class SyncTopologyResponse(BaseModel):
    """Response from topology sync operation."""
    synced_count: int
    failed_count: int
    total_nodes: int
    errors: list[str]
    synced_nodes: list[str]
    success: bool


class NodeTopologyResponse(BaseModel):
    """Topology information for a single node."""
    node_name: str
    su_id: Optional[str]
    rack_id: Optional[str]
    rail_id: Optional[str]
    roce_ready: bool
    zone: Optional[str]
    region: Optional[str]


class VerifySyncResponse(BaseModel):
    """Health check response for topology sync status."""
    total_nodes: int
    labeled_nodes: int
    unlabeled_nodes: int
    unlabeled_node_names: list[str]
    sync_health: str  # "HEALTHY", "DEGRADED", "CRITICAL"


@router.post("/sync-topology/{project_id}", response_model=SyncTopologyResponse)
def sync_topology(project_id: str) -> SyncTopologyResponse:
    """Trigger topology sync for all nodes in project.
    
    This is the main entry point for topology synchronization.
    It queries Firestore for all COMPUTE nodes and applies topology labels
    to corresponding Kubernetes nodes.
    
    **When to call:**
    - After new nodes join the cluster
    - Periodically (every 5 minutes via cron)
    - After LLDP validation completes
    - After hardware changes or node replacement
    - For manual troubleshooting
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8000/k8s-topology-sync/sync-topology/my-project
    ```
    
    Args:
        project_id: Firestore project ID to sync
        
    Returns:
        SyncTopologyResponse with sync results
        
    Raises:
        HTTPException 500: If Firestore client not initialized or sync fails
        HTTPException 404: If project has no compute nodes
    """
    if db is None:
        raise HTTPException(
            status_code=500,
            detail="Firestore client not initialized. Check FIREBASE_ADMIN_CREDENTIALS."
        )
    
    try:
        print(f"\n{'='*70}")
        print(f"📡 API: Received topology sync request for project {project_id}")
        print(f"{'='*70}")
        
        sync = K8sTopologySync(project_id, db)
        result = sync.sync_all_nodes()
        
        # Determine success based on whether any nodes were synced
        success = result["synced_count"] > 0
        
        if result["total_nodes"] == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No compute nodes found for project {project_id}. "
                       "Have nodes completed ZTP and joined Kubernetes?"
            )
        
        return SyncTopologyResponse(
            synced_count=result["synced_count"],
            failed_count=result["failed_count"],
            total_nodes=result["total_nodes"],
            errors=result["errors"],
            synced_nodes=result["synced_nodes"],
            success=success
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Topology sync failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Topology sync failed: {str(e)}"
        )


@router.get("/node-topology/{node_name}", response_model=NodeTopologyResponse)
def get_node_topology(node_name: str) -> NodeTopologyResponse:
    """Get topology labels for a specific node.
    
    Useful for debugging and validation. Returns the current topology
    labels applied to a Kubernetes node.
    
    **Example:**
    ```bash
    curl http://localhost:8000/k8s-topology-sync/node-topology/dgx-su1-r02-s05
    ```
    
    Args:
        node_name: Kubernetes node name
        
    Returns:
        NodeTopologyResponse with topology labels
        
    Raises:
        HTTPException 404: If node not found in Kubernetes
        HTTPException 500: If kubectl fails
    """
    if db is None:
        raise HTTPException(
            status_code=500,
            detail="Firestore client not initialized."
        )
    
    try:
        sync = K8sTopologySync("default", db)  # project_id not needed for read
        topology = sync.get_node_topology(node_name)
        
        return NodeTopologyResponse(
            node_name=node_name,
            su_id=topology["su_id"],
            rack_id=topology["rack_id"],
            rail_id=topology["rail_id"],
            roce_ready=topology["roce_ready"],
            zone=topology["zone"],
            region=topology["region"]
        )
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Node {node_name} not found: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get node topology: {str(e)}"
        )


@router.get("/verify-sync/{project_id}", response_model=VerifySyncResponse)
def verify_sync(project_id: str) -> VerifySyncResponse:
    """Verify that all K8s nodes have topology labels.
    
    This is a health check endpoint. Use it to ensure topology sync
    is working correctly.
    
    **Health Status:**
    - HEALTHY: All nodes labeled
    - DEGRADED: 1-25% unlabeled
    - CRITICAL: >25% unlabeled
    
    **Example:**
    ```bash
    curl http://localhost:8000/k8s-topology-sync/verify-sync/my-project
    ```
    
    Args:
        project_id: Firestore project ID
        
    Returns:
        VerifySyncResponse with health status
    """
    if db is None:
        raise HTTPException(
            status_code=500,
            detail="Firestore client not initialized."
        )
    
    try:
        sync = K8sTopologySync(project_id, db)
        result = sync.verify_all_nodes_labeled()
        
        # Determine health status
        if result["unlabeled_nodes"] == 0:
            health = "HEALTHY"
        elif result["unlabeled_nodes"] / result["total_nodes"] <= 0.25:
            health = "DEGRADED"
        else:
            health = "CRITICAL"
        
        return VerifySyncResponse(
            total_nodes=result["total_nodes"],
            labeled_nodes=result["labeled_nodes"],
            unlabeled_nodes=result["unlabeled_nodes"],
            unlabeled_node_names=result["unlabeled_node_names"],
            sync_health=health
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Verification failed: {str(e)}"
        )


@router.post("/sync-single-node/{node_name}")
def sync_single_node(node_name: str, project_id: str) -> Dict:
    """Sync topology for a single node (faster than full sync).
    
    Useful for:
    - After node replacement
    - After hardware changes
    - After LLDP re-validation
    - Troubleshooting individual nodes
    
    **Example:**
    ```bash
    curl -X POST "http://localhost:8000/k8s-topology-sync/sync-single-node/dgx-su1-r02-s05?project_id=my-project"
    ```
    
    Args:
        node_name: Node to sync
        project_id: Firestore project ID (query param)
        
    Returns:
        Dict with sync status
    """
    if db is None:
        raise HTTPException(
            status_code=500,
            detail="Firestore client not initialized."
        )
    
    try:
        # Query Firestore for this specific node
        nodes_ref = db.collection("live_infrastructure")
        query = (
            nodes_ref
            .where("projectId", "==", project_id)
            .where("tier", "==", "COMPUTE")
            .where("hostname", "==", node_name)
            .limit(1)
        )
        
        node_docs = list(query.stream())
        
        if not node_docs:
            # Try case-insensitive search
            all_nodes = (
                nodes_ref
                .where("projectId", "==", project_id)
                .where("tier", "==", "COMPUTE")
                .stream()
            )
            
            for doc in all_nodes:
                data = doc.to_dict()
                hostname = data.get("hostname", "").lower()
                if hostname == node_name.lower():
                    node_docs = [doc]
                    break
        
        if not node_docs:
            raise HTTPException(
                status_code=404,
                detail=f"Node {node_name} not found in Firestore for project {project_id}"
            )
        
        # Trigger sync for this one node
        sync = K8sTopologySync(project_id, db)
        result = sync.sync_all_nodes()  # Will only process nodes in Firestore query
        
        return {
            "node_name": node_name,
            "success": result["synced_count"] > 0,
            "message": f"Synced {result['synced_count']} node(s)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Single node sync failed: {str(e)}"
        )
