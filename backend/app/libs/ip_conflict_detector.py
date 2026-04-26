"""IP Conflict Detection - Validates IP Allocation Integrity

Ensures no overlapping subnets or duplicate IPs across:
- Multi-SU clusters
- Multiple planes
- Management vs data networks

Detects conflicts BEFORE deployment (Day 0) rather than during Day 1.
"""

from typing import Dict, List, Set, Tuple, Optional
from app.libs.cluster_topology import ClusterTopology
from app.libs.ip_schema_orchestrator import IPSchemaOrchestrator


class IPConflict:
    """Represents a detected IP conflict."""
    
    def __init__(
        self,
        conflict_type: str,
        ip_address: str,
        device1: str,
        device2: str,
        severity: str,
        resolution: str
    ):
        self.conflict_type = conflict_type  # DUPLICATE_IP, OVERLAPPING_SUBNET, MGMT_DATA_COLLISION
        self.ip_address = ip_address
        self.device1 = device1
        self.device2 = device2
        self.severity = severity  # CRITICAL, HIGH, MEDIUM
        self.resolution = resolution  # How to fix
    
    def to_dict(self) -> Dict:
        return {
            "conflict_type": self.conflict_type,
            "ip_address": self.ip_address,
            "device1": self.device1,
            "device2": self.device2,
            "severity": self.severity,
            "resolution": self.resolution
        }


class IPConflictDetector:
    """Detects IP allocation conflicts before deployment."""
    
    def __init__(self, topology: ClusterTopology, orchestrator: IPSchemaOrchestrator):
        """Initialize conflict detector.
        
        Args:
            topology: Cluster topology
            orchestrator: IP orchestrator for allocation logic
        """
        self.topology = topology
        self.orchestrator = orchestrator
        print("🔍 IPConflictDetector initialized")
    
    def scan_gpu_ips(self) -> Tuple[Dict[str, List[str]], List[IPConflict]]:
        """Scan all GPU IP allocations for conflicts.
        
        Returns:
            Tuple of (ip_map, conflicts)
            - ip_map: Dict mapping IP -> list of devices using it
            - conflicts: List of IPConflict objects
        """
        ip_map: Dict[str, List[str]] = {}
        conflicts: List[IPConflict] = []
        
        # Iterate through all GPUs in cluster
        for rack_idx in range(1, self.topology.R + 1):
            for server_idx in range(1, self.topology.S + 1):
                for gpu_idx in range(self.topology.G):
                    for tail_idx in range(self.topology.N):
                        # Generate IP for this GPU
                        ip_data = self.orchestrator.generate_gpu_ip(
                            rack_idx=rack_idx,
                            server_idx=server_idx,
                            gpu_idx=gpu_idx,
                            tail_idx=tail_idx
                        )
                        
                        gpu_ip = ip_data["gpu_ip"]
                        device_name = f"Rack{rack_idx}-Srv{server_idx}-GPU{gpu_idx}-Tail{tail_idx}"
                        
                        # Track IP usage
                        if gpu_ip not in ip_map:
                            ip_map[gpu_ip] = []
                        ip_map[gpu_ip].append(device_name)
        
        # Find duplicates
        for ip, devices in ip_map.items():
            if len(devices) > 1:
                conflicts.append(IPConflict(
                    conflict_type="DUPLICATE_IP",
                    ip_address=ip,
                    device1=devices[0],
                    device2=devices[1],
                    severity="CRITICAL",
                    resolution=f"Fix IP allocation formula - {len(devices)} devices share same IP"
                ))
        
        return ip_map, conflicts
    
    def check_management_collisions(self, mgmt_ips: Dict[str, str]) -> List[IPConflict]:
        """Check if management IPs collide with data plane IPs.
        
        Args:
            mgmt_ips: Dict mapping device_name -> management IP
            
        Returns:
            List of conflicts
        """
        conflicts: List[IPConflict] = []
        
        # Get all GPU IPs
        ip_map, _ = self.scan_gpu_ips()
        gpu_ips = set(ip_map.keys())
        
        # Check each management IP
        for device_name, mgmt_ip in mgmt_ips.items():
            if mgmt_ip in gpu_ips:
                gpu_devices = ip_map[mgmt_ip]
                conflicts.append(IPConflict(
                    conflict_type="MGMT_DATA_COLLISION",
                    ip_address=mgmt_ip,
                    device1=device_name,
                    device2=gpu_devices[0],
                    severity="CRITICAL",
                    resolution="Management IP overlaps with GPU data plane IP"
                ))
        
        return conflicts
    
    def validate_subnet_isolation(self) -> List[IPConflict]:
        """Validate that subnets don't overlap across planes/SUs.
        
        Returns:
            List of conflicts
        """
        conflicts: List[IPConflict] = []
        subnets_seen: Set[str] = set()
        
        # Check /31 subnets for each GPU pair
        for rack_idx in range(1, self.topology.R + 1):
            for server_idx in range(1, self.topology.S + 1):
                for gpu_idx in range(self.topology.G):
                    for tail_idx in range(self.topology.N):
                        ip_data = self.orchestrator.generate_gpu_ip(
                            rack_idx, server_idx, gpu_idx, tail_idx
                        )
                        
                        subnet = ip_data["subnet"]
                        device_name = f"Rack{rack_idx}-Srv{server_idx}-GPU{gpu_idx}-Tail{tail_idx}"
                        
                        if subnet in subnets_seen:
                            conflicts.append(IPConflict(
                                conflict_type="OVERLAPPING_SUBNET",
                                ip_address=subnet,
                                device1=device_name,
                                device2="Previous allocation",
                                severity="CRITICAL",
                                resolution="Subnet reused - fix IP allocation formula"
                            ))
                        
                        subnets_seen.add(subnet)
        
        return conflicts
    
    def run_full_scan(self, mgmt_ips: Optional[Dict[str, str]] = None) -> Dict:
        """Run complete conflict detection scan.
        
        Args:
            mgmt_ips: Optional management IP mappings
            
        Returns:
            Dict with scan results
        """
        print("🔍 Running full IP conflict scan...")
        
        # Scan GPU IPs
        ip_map, gpu_conflicts = self.scan_gpu_ips()
        
        # Check management collisions
        mgmt_conflicts = []
        if mgmt_ips:
            mgmt_conflicts = self.check_management_collisions(mgmt_ips)
        
        # Validate subnet isolation
        subnet_conflicts = self.validate_subnet_isolation()
        
        # Combine all conflicts
        all_conflicts = gpu_conflicts + mgmt_conflicts + subnet_conflicts
        
        # Summary
        critical_count = len([c for c in all_conflicts if c.severity == "CRITICAL"])
        
        result = {
            "status": "CLEAN" if len(all_conflicts) == 0 else "CONFLICTS_FOUND",
            "total_ips_allocated": len(ip_map),
            "total_conflicts": len(all_conflicts),
            "critical_conflicts": critical_count,
            "conflicts_by_type": {
                "DUPLICATE_IP": len([c for c in all_conflicts if c.conflict_type == "DUPLICATE_IP"]),
                "OVERLAPPING_SUBNET": len([c for c in all_conflicts if c.conflict_type == "OVERLAPPING_SUBNET"]),
                "MGMT_DATA_COLLISION": len([c for c in all_conflicts if c.conflict_type == "MGMT_DATA_COLLISION"])
            },
            "conflicts": [c.to_dict() for c in all_conflicts]
        }
        
        if result["status"] == "CLEAN":
            print(f"✅ No conflicts detected. {result['total_ips_allocated']} IPs validated.")
        else:
            print(f"❌ {result['total_conflicts']} conflicts found ({critical_count} CRITICAL)")
        
        return result
