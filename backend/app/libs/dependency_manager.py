"""Dependency Manager - Tier-Based Provisioning Sequencing

Enforces power-on order: BACKEND_FABRIC → STORAGE → COMPUTE
Prevents "power storm" scenarios where compute boots before infrastructure ready.

Architecture:
- Global state machine per project
- Tier health checks via Firestore queries
- Gatekeeper integration with DHCPScraper
- Emergency override with audit trail
"""

from google.cloud import firestore
from typing import Dict, List, Optional
from datetime import datetime, timezone
from enum import Enum
from app.libs.firestore_scoping import get_scoped_collection


class Tier(str, Enum):
    """Infrastructure tiers in dependency order."""
    BACKEND_FABRIC = "BACKEND_FABRIC"  # InfiniBand, high-speed Ethernet
    STORAGE = "STORAGE"                # NFS, Lustre, Ceph
    COMPUTE = "COMPUTE"                # GPU nodes


class TierHealth(str, Enum):
    """Tier health states."""
    NOT_STARTED = "NOT_STARTED"      # No devices provisioned yet
    IN_PROGRESS = "IN_PROGRESS"      # Some devices operational
    READY = "READY"                  # All devices operational, dependencies met
    DEGRADED = "DEGRADED"            # Some devices down but tier functional
    BLOCKED = "BLOCKED"              # Dependency tier not ready


class DependencyManager:
    """Manages tier-based provisioning dependencies."""
    
    # Tier dependency graph
    TIER_DEPENDENCIES = {
        Tier.BACKEND_FABRIC: [],                    # No dependencies
        Tier.STORAGE: [Tier.BACKEND_FABRIC],        # Needs network
        Tier.COMPUTE: [Tier.BACKEND_FABRIC, Tier.STORAGE]  # Needs both
    }
    
    # Minimum health thresholds for "READY" state
    HEALTH_THRESHOLDS = {
        Tier.BACKEND_FABRIC: 1.0,   # 100% of switches must be OPERATIONAL
        Tier.STORAGE: 0.95,         # 95% of storage nodes must be healthy
        Tier.COMPUTE: 0.0           # Compute has no health requirement (it's the final tier)
    }
    
    def __init__(self, project_id: str, db_client: Optional[firestore.Client] = None, customer_id: str = "default"):
        """Initialize dependency manager.
        
        Args:
            project_id: Firestore project ID
            db_client: Firestore client (optional, creates new if None)
            customer_id: Customer ID for data isolation
        """
        self.project_id = project_id
        self.db = db_client or firestore.Client()
        self.customer_id = customer_id
        print(f"🔒 DependencyManager initialized for project {project_id}, customer {customer_id}")
    
    def get_tier_health(self, tier: Tier) -> Dict:
        """Calculate health metrics for a specific tier.
        
        Args:
            tier: Infrastructure tier to check
            
        Returns:
            Dict with keys:
            - health: TierHealth enum
            - total_devices: Total devices in tier
            - operational_devices: Devices in OPERATIONAL state
            - percentage: Health percentage (0-100)
            - blocking_reason: Why tier is blocked (if BLOCKED)
        """
        # Query live_infrastructure for this tier (customer-scoped)
        devices_ref = get_scoped_collection(self.db, self.customer_id, "live_infrastructure")
        
        # Map tier to device roles
        role_mapping = {
            Tier.BACKEND_FABRIC: ["LEAF", "SPINE", "CORE"],
            Tier.STORAGE: ["STORAGE_NODE", "NFS_SERVER", "CEPH_OSD"],
            Tier.COMPUTE: ["GPU_NODE", "COMPUTE_NODE"]
        }
        
        roles = role_mapping.get(tier, [])
        if not roles:
            return {
                "health": TierHealth.NOT_STARTED,
                "total_devices": 0,
                "operational_devices": 0,
                "percentage": 0.0,
                "blocking_reason": "Unknown tier"
            }
        
        # Count total devices
        total_query = devices_ref.where("role", "in", roles).where("project_id", "==", self.project_id)
        total_devices = len(list(total_query.stream()))
        
        if total_devices == 0:
            return {
                "health": TierHealth.NOT_STARTED,
                "total_devices": 0,
                "operational_devices": 0,
                "percentage": 0.0,
                "blocking_reason": "No devices found in tier"
            }
        
        # Count operational devices
        operational_query = (
            devices_ref
            .where("role", "in", roles)
            .where("project_id", "==", self.project_id)
            .where("status", "==", "OPERATIONAL")
        )
        operational_devices = len(list(operational_query.stream()))
        
        percentage = (operational_devices / total_devices) * 100
        threshold = self.HEALTH_THRESHOLDS[tier] * 100
        
        # Determine health state
        if percentage >= threshold:
            health = TierHealth.READY
            blocking_reason = None
        elif operational_devices > 0:
            health = TierHealth.IN_PROGRESS
            blocking_reason = f"Only {percentage:.1f}% operational (need {threshold:.1f}%)"
        else:
            health = TierHealth.NOT_STARTED
            blocking_reason = "No devices operational yet"
        
        return {
            "health": health,
            "total_devices": total_devices,
            "operational_devices": operational_devices,
            "percentage": percentage,
            "blocking_reason": blocking_reason
        }
    
    def check_dependencies(self, device_tier: Tier) -> Dict:
        """Check if all dependency tiers are ready for device to provision.
        
        Args:
            device_tier: Tier of device requesting provisioning
            
        Returns:
            Dict with keys:
            - allowed: Boolean, can device provision?
            - tier_health: Health status of each dependency tier
            - blocking_tiers: List of tiers blocking provisioning
            - message: Human-readable explanation
        """
        dependencies = self.TIER_DEPENDENCIES.get(device_tier, [])
        
        if not dependencies:
            # No dependencies (e.g., BACKEND_FABRIC)
            return {
                "allowed": True,
                "tier_health": {},
                "blocking_tiers": [],
                "message": f"{device_tier} has no dependencies. Provisioning allowed."
            }
        
        tier_health = {}
        blocking_tiers = []
        
        for dep_tier in dependencies:
            health_data = self.get_tier_health(dep_tier)
            tier_health[dep_tier] = health_data
            
            if health_data["health"] != TierHealth.READY:
                blocking_tiers.append({
                    "tier": dep_tier,
                    "reason": health_data["blocking_reason"],
                    "percentage": health_data["percentage"]
                })
        
        allowed = len(blocking_tiers) == 0
        
        if allowed:
            message = f"All dependencies ready. {device_tier} provisioning allowed."
        else:
            blocking_names = [bt["tier"] for bt in blocking_tiers]
            message = f"{device_tier} provisioning blocked. Waiting for: {', '.join(blocking_names)}"
        
        return {
            "allowed": allowed,
            "tier_health": tier_health,
            "blocking_tiers": blocking_tiers,
            "message": message
        }
    
    def check_override_permission(self, device_tier: Tier, override_token: Optional[str] = None) -> Dict:
        """Check if emergency override is permitted.
        
        Args:
            device_tier: Tier attempting override
            override_token: Emergency override token (from CTO/Lead)
            
        Returns:
            Dict with keys:
            - permitted: Boolean
            - reason: Explanation
            - audit_required: Boolean, must log this decision
        """
        # In production, validate override_token against secrets
        # For now, simple token check
        
        valid_override = override_token == "EMERGENCY_OVERRIDE_AUTHORIZED"
        
        if valid_override:
            return {
                "permitted": True,
                "reason": "Emergency override token validated",
                "audit_required": True
            }
        else:
            return {
                "permitted": False,
                "reason": "Invalid or missing override token",
                "audit_required": False
            }
    
    def create_dependency_block_alert(
        self,
        device_name: str,
        device_tier: Tier,
        blocking_tiers: List[Dict]
    ) -> str:
        """Create Firestore alert for dependency block.
        
        Args:
            device_name: Name of blocked device
            device_tier: Tier of blocked device
            blocking_tiers: List of blocking tier data
            
        Returns:
            Alert ID
        """
        alert_ref = self.db.collection("provisioning_alerts").document()
        
        alert_data = {
            "project_id": self.project_id,
            "type": "DEPENDENCY_BLOCK",
            "severity": "HIGH",
            "device_name": device_name,
            "device_tier": device_tier,
            "blocking_tiers": blocking_tiers,
            "status": "UNRESOLVED",
            "created_at": datetime.now(timezone.utc),
            "message": f"{device_name} ({device_tier}) blocked by tier dependencies"
        }
        
        alert_ref.set(alert_data)
        print(f"🚨 Created dependency block alert: {alert_ref.id}")
        
        return alert_ref.id
    
    def get_cluster_readiness(self) -> Dict:
        """Get overall cluster readiness status.
        
        Returns:
            Dict with tier-by-tier readiness breakdown
        """
        all_tiers = [Tier.BACKEND_FABRIC, Tier.STORAGE, Tier.COMPUTE]
        
        readiness = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tiers": {}
        }
        
        for tier in all_tiers:
            health = self.get_tier_health(tier)
            deps = self.check_dependencies(tier)
            
            readiness["tiers"][tier] = {
                "health": health,
                "dependencies": deps,
                "can_provision": deps["allowed"]
            }
        
        return readiness
