"""Kubernetes Provisioner for Bare-Metal GPU Clusters

✅ Subprocess-based implementation (no external packages needed)

Automates K3s worker node registration after ZTP provisioning.
Uses system `ssh` and `kubectl` binaries via subprocess.

**Integration with ZTP:**
After DHCPScraper provisions a compute node with OS and IP:
1. DHCPScraper calls k8s_provisioner.join_worker_node()
2. Provisioner SSHs to node via subprocess and installs K3s agent
3. Node auto-registers to cluster
4. **NEW: K8sTopologySync applies SU/Rack/Rail labels from Firestore**
5. GPU Device Plugin exposes GPUs to scheduler

**Security:**
- Uses SSH key-based auth (no passwords)
- K3s token stored as secret (K3S_TOKEN env var)
- Control plane IP from environment

Example:
    provisioner = K8sProvisioner()
    await provisioner.join_worker_node(
        node_ip="10.244.1.5",
        node_hostname="SU1-RACK01-SRV01",
        tier="COMPUTE"
    )
"""

import os
import asyncio
import subprocess
import json
import time
from fastapi import HTTPException
from google.cloud import firestore
from app.libs.k8s_topology_sync import K8sTopologySync


class K8sProvisioner:
    """Manages Kubernetes cluster node lifecycle for GPU cloud."""
    
    def __init__(self):
        """Initialize provisioner with cluster credentials."""
        # K3s authentication token (shared secret)
        self.k3s_token = os.environ.get("K3S_TOKEN")
        if not self.k3s_token:
            print("⚠️ K3S_TOKEN not set - using placeholder for development")
            self.k3s_token = "development-token-replace-in-production"
        
        # Control plane endpoint (K8s API server)
        self.control_plane_ip = os.environ.get("K3S_CONTROL_PLANE_IP", "10.0.0.10")
        
        # SSH configuration
        self.ssh_key_path = os.environ.get("SSH_PRIVATE_KEY_PATH", "/root/.ssh/id_rsa")
        self.ssh_user = os.environ.get("SSH_USER", "root")
        
        # Kubeconfig location
        self.kubeconfig = os.environ.get("KUBECONFIG", os.path.expanduser("~/.kube/config"))
        
        # Initialize Firestore for topology sync
        try:
            firebase_creds = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
            if firebase_creds:
                creds = json.loads(firebase_creds)
                self.db = firestore.Client.from_service_account_info(creds)
            else:
                self.db = firestore.Client()
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize Firestore client: {e}")
            self.db = None
        
        print("✅ K8sProvisioner initialized")
        print(f"   Control Plane: {self.control_plane_ip}")
        print(f"   SSH User: {self.ssh_user}")
    
    def _run_ssh_command(
        self,
        target_ip: str,
        command: str,
        timeout: int = 60
    ) -> tuple[int, str, str]:
        """Execute command on remote node via SSH subprocess.
        
        Args:
            target_ip: Target node IP
            command: Shell command to execute
            timeout: Command timeout in seconds
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", f"ConnectTimeout={timeout}",
            f"root@{target_ip}",
            command
        ]
        
        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            return result.returncode, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return -1, "", f"SSH command timed out after {timeout}s"
        except Exception as e:
            return -1, "", str(e)
    
    def _run_kubectl(self, args: list[str], timeout: int = 30) -> str:
        """Execute kubectl command via subprocess.
        
        Args:
            args: kubectl arguments (e.g., ["get", "nodes"])
            timeout: Command timeout in seconds
            
        Returns:
            stdout as string
            
        Raises:
            HTTPException if command fails
        """
        kubectl_cmd = ["kubectl"] + args
        
        try:
            result = subprocess.run(
                kubectl_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"kubectl command failed: {result.stderr}"
                )
            
            return result.stdout
            
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=504,
                detail=f"kubectl command timed out after {timeout}s"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"kubectl error: {str(e)}"
            )
    
    async def deploy_control_plane(self, control_plane_node_ip: str) -> dict:
        """Deploy K3s control plane on admin node.
        
        This is a ONE-TIME operation to bootstrap the cluster.
        After this, all other nodes join as workers.
        
        Args:
            control_plane_node_ip: IP of admin node to become control plane
            
        Returns:
            Dict with cluster status and kubeconfig
        """
        print(f"🚀 Deploying K3s control plane on {control_plane_node_ip}")
        
        # Install K3s in server mode
        install_cmd = f"""
        curl -sfL https://get.k3s.io | sh -s - server \
          --cluster-init \
          --disable traefik \
          --disable servicelb \
          --write-kubeconfig-mode 644 \
          --node-label tier=control-plane \
          --node-label topology.ai-factory/provisioned-by=ztp \
          --token {self.k3s_token}
        """
        
        exit_code, stdout, stderr = self._run_ssh_command(
            control_plane_node_ip,
            install_cmd,
            timeout=300
        )
        
        if exit_code != 0:
            print(f"❌ Failed to deploy control plane: {stderr}")
            return {
                "status": "FAILED",
                "error": stderr
            }
        
        # Wait for API server to be ready
        print("⏳ Waiting for K8s API server to start...")
        await asyncio.sleep(30)
        
        # Retrieve kubeconfig
        exit_code, kubeconfig, stderr = self._run_ssh_command(
            control_plane_node_ip,
            "cat /etc/rancher/k3s/k3s.yaml",
            timeout=30
        )
        
        if exit_code != 0:
            print(f"⚠️ Failed to retrieve kubeconfig: {stderr}")
            kubeconfig = "Not available"
        
        return {
            "status": "SUCCESS",
            "control_plane_ip": control_plane_node_ip,
            "kubeconfig": kubeconfig
        }
    
    async def join_worker_node(
        self,
        node_ip: str,
        node_hostname: str,
        tier: str = "COMPUTE",
        gpu_count: int = 8,
        project_id: str = "default"
    ) -> dict:
        """Join a worker node to the K8s cluster after ZTP provisioning.
        
        This is called by DHCPScraper after OS installation completes.
        
        Args:
            node_ip: Management IP of the node (from DHCP)
            node_hostname: Hostname (e.g., SU1-RACK01-SRV01)
            tier: COMPUTE, STORAGE, or ADMIN
            gpu_count: Number of GPUs on node (for validation)
            project_id: Firestore project ID for topology sync
            
        Returns:
            Dict with join status and node info
        """
        print(f"🔗 Joining node {node_hostname} ({node_ip}) to K8s cluster")
        
        # Only join COMPUTE nodes for now (GPU workers)
        if tier != "COMPUTE":
            print(f"⏭️ Skipping K8s join for {tier} tier node")
            return {"status": "SKIPPED", "reason": f"{tier} nodes don't join K8s cluster"}
        
        # Install K3s agent
        install_cmd = f"""
        curl -sfL https://get.k3s.io | K3S_URL=https://{self.control_plane_ip}:6443 \
        K3S_TOKEN={self.k3s_token} \
        sh -s - agent \
          --node-name {node_hostname} \
          --node-label topology.ai-factory/provisioned-by=dhcp-scraper \
          --node-label topology.ai-factory/tier=compute \
          --node-label gpu.nvidia.com/expected-count={gpu_count}
        """
        
        print(f"📦 Installing K3s agent on {node_hostname}...")
        exit_code, stdout, stderr = self._run_ssh_command(
            node_ip,
            install_cmd,
            timeout=300
        )
        
        if exit_code != 0:
            print(f"❌ Failed to join node {node_hostname}: {stderr}")
            return {
                "status": "FAILED",
                "node_hostname": node_hostname,
                "error": stderr
            }
        
        # Wait for node to register
        print(f"⏳ Waiting for node {node_hostname} to register...")
        if await self._wait_for_node_registered(node_hostname, timeout=120):
            # **NEW: Trigger topology sync after node joins**
            if self.db:
                print(f"🔗 Triggering topology sync for {node_hostname}...")
                try:
                    sync = K8sTopologySync(project_id, self.db)
                    result = sync.sync_all_nodes()
                    
                    if result["synced_count"] > 0:
                        print(f"✅ Topology labels applied to {result['synced_count']} node(s)")
                    else:
                        print(f"⚠️ Topology sync ran but labeled 0 nodes. Errors: {result['errors']}")
                except Exception as e:
                    print(f"⚠️ Topology sync failed (non-fatal): {e}")
                    # Don't fail the join if topology sync fails
            else:
                print("⚠️ Skipping topology sync - Firestore not initialized")
            
            return {
                "status": "SUCCESS",
                "node_hostname": node_hostname,
                "node_ip": node_ip,
                "message": f"Node {node_hostname} joined cluster successfully"
            }
        else:
            return {
                "status": "TIMEOUT",
                "node_hostname": node_hostname,
                "message": "Node installed K3s but didn't register within timeout"
            }
    
    async def _wait_for_node_registered(
        self,
        node_hostname: str,
        timeout: int = 120
    ) -> bool:
        """Wait for node to appear in K8s cluster.
        
        Args:
            node_hostname: Expected node name
            timeout: Max wait time in seconds
            
        Returns:
            True if node registered, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Try to get the node
                result = subprocess.run(
                    ["kubectl", "get", "node", node_hostname, "-o", "json"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    # Node exists, check if Ready
                    node_data = json.loads(result.stdout)
                    conditions = node_data.get("status", {}).get("conditions", [])
                    
                    for condition in conditions:
                        if condition.get("type") == "Ready" and condition.get("status") == "True":
                            print(f"✅ Node {node_hostname} is Ready")
                            return True
                    
                    print(f"⏳ Node {node_hostname} exists but not Ready yet")
                else:
                    print(f"⏳ Node {node_hostname} not found yet, waiting...")
                
            except Exception as e:
                print(f"⚠️ Error checking node status: {e}")
            
            await asyncio.sleep(5)
        
        print(f"❌ Timeout waiting for node {node_hostname} to register")
        return False
    
    async def get_cluster_status(self) -> dict:
        """Get cluster health metrics.
        
        Returns:
            Dict with cluster status
        """
        try:
            nodes_output = self._run_kubectl(["get", "nodes"])
            
            # Parse node count
            lines = nodes_output.strip().split("\n")
            total_nodes = len(lines) - 1  # Subtract header
            
            ready_nodes = 0
            for line in lines[1:]:
                if "Ready" in line:
                    ready_nodes += 1
            
            # Try to get GPU count (requires GPU device plugin)
            total_gpus = 0
            try:
                gpu_output = self._run_kubectl([
                    "get", "nodes",
                    "-o=jsonpath={range .items[*]}{.status.capacity.nvidia\\.com/gpu}{'\\n'}{end}"
                ])
                
                for gpu_count_str in gpu_output.strip().split("\n"):
                    if gpu_count_str:
                        total_gpus += int(gpu_count_str)
            except Exception:
                pass  # GPU plugin not installed yet
            
            return {
                "total_nodes": total_nodes,
                "ready_nodes": ready_nodes,
                "total_gpus": total_gpus,
                "control_plane_ip": self.control_plane_ip
            }
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to get cluster status: {str(e)}"
            )
    
    def deploy_gpu_device_plugin(self) -> dict:
        """Deploy NVIDIA GPU Device Plugin as DaemonSet.
        
        This enables K8s to discover and schedule GPUs on worker nodes.
        Uses official NVIDIA Device Plugin from nvidia/k8s-device-plugin.
        
        Returns:
            Dict with deployment status
        """
        print("\n🎮 Deploying NVIDIA GPU Device Plugin...")
        
        # NVIDIA Device Plugin DaemonSet manifest
        manifest = """
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: nvidia-device-plugin-daemonset
  namespace: kube-system
spec:
  selector:
    matchLabels:
      name: nvidia-device-plugin-ds
  updateStrategy:
    type: RollingUpdate
  template:
    metadata:
      labels:
        name: nvidia-device-plugin-ds
    spec:
      tolerations:
      - key: nvidia.com/gpu
        operator: Exists
        effect: NoSchedule
      # Only run on nodes with GPUs (COMPUTE tier)
      nodeSelector:
        topology.ai-factory/tier: compute
      priorityClassName: system-node-critical
      containers:
      - image: nvcr.io/nvidia/k8s-device-plugin:v0.14.5
        name: nvidia-device-plugin-ctr
        args:
          - "--fail-on-init-error=false"
          - "--pass-device-specs=true"
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop: ["ALL"]
        volumeMounts:
        - name: device-plugin
          mountPath: /var/lib/kubelet/device-plugins
      volumes:
      - name: device-plugin
        hostPath:
          path: /var/lib/kubelet/device-plugins
---
apiVersion: v1
kind: RuntimeClass
metadata:
  name: nvidia
handler: nvidia
"""
        
        try:
            # Apply manifest via kubectl
            result = subprocess.run(
                ["kubectl", "apply", "-f", "-"],
                input=manifest.encode(),
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print("✅ GPU Device Plugin DaemonSet created")
                print("⏳ Waiting for pods to start...")
                
                # Wait for daemonset to be ready
                time.sleep(10)
                
                # Check daemonset status
                ds_status = subprocess.run(
                    ["kubectl", "get", "daemonset", "-n", "kube-system", 
                     "nvidia-device-plugin-daemonset", "-o", "json"],
                    capture_output=True,
                    timeout=10
                )
                
                if ds_status.returncode == 0:
                    import json
                    ds_data = json.loads(ds_status.stdout)
                    desired = ds_data.get("status", {}).get("desiredNumberScheduled", 0)
                    ready = ds_data.get("status", {}).get("numberReady", 0)
                    
                    print(f"📊 DaemonSet Status: {ready}/{desired} pods ready")
                    
                    return {
                        "status": "SUCCESS",
                        "desired_pods": desired,
                        "ready_pods": ready,
                        "message": f"GPU Device Plugin deployed ({ready}/{desired} ready)"
                    }
                else:
                    return {
                        "status": "SUCCESS",
                        "message": "DaemonSet created but status check failed (may be starting)"
                    }
            else:
                error_msg = result.stderr.decode()
                print(f"⚠️ Failed to deploy GPU Device Plugin: {error_msg}")
                return {
                    "status": "FAILED",
                    "error": error_msg
                }
                
        except subprocess.TimeoutExpired:
            return {
                "status": "TIMEOUT",
                "message": "GPU Device Plugin deployment timed out"
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e)
            }
