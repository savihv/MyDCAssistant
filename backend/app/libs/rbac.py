from datetime import datetime, timezone
from typing import Dict, Any
from google.cloud import firestore  # type: ignore

class RBACManager:
    """
    Role-Based Access Control (RBAC) Manager for TechTalk Enterprise SaaS.
    
    Manages permissions for the three primary roles:
    - Admin: Full access to the project, can manage users and download ZTP configs.
    - Network Engineer: Can view real-time topology, validate cabling, download switch configs.
    - Server Admin: Can view compute node status and schedule OS installations/K8s joins.
    - Read-Only: Can view dashboards and export reports.
    
    Permissions are stored in the customer's /users collection in Firestore.
    """
    
    # Define role permissions matrix
    ROLE_PERMISSIONS = {
        "admin": [
            "manage_users",
            "download_configs",
            "view_topology",
            "validate_cabling",
            "view_dashboards",
            "manage_billing",
            "export_reports"
        ],
        "network_engineer": [
            "view_topology",
            "download_configs",
            "validate_cabling",
            "view_dashboards"
        ],
        "server_admin": [
            "view_compute_status",
            "download_server_configs",
            "trigger_provisioning",
            "view_dashboards"
        ],
        "read_only": [
            "view_dashboards",
            "export_reports"
        ]
    }
    
    def __init__(self, db_client: firestore.Client):
        self.db = db_client
        
    def check_permission(
        self,
        user_email: str,
        customer_id: str,
        action: str
    ) -> bool:
        """
        Check if a user has permission to perform a specific action within a customer tenant.
        
        Args:
            user_email: Email address of the user attempting the action
            customer_id: The Enterprise Customer Tenant ID
            action: The capability string (e.g., 'download_configs')
            
        Returns:
            True if permitted, False otherwise
        """
        # System Admins (superusers) always have access across all tenants
        if self._is_system_admin(user_email):
            return True
            
        # Query the user's role in the customer's user collection
        users_ref = self.db.collection(f"customers/{customer_id}/users")
        query = users_ref.where("email", "==", user_email).limit(1).stream()
        
        user_role = "read_only"  # Default fallback
        user_found = False
        
        for doc in query:
            user_data = doc.to_dict()
            user_role = user_data.get("role", "read_only").lower()
            user_found = True
            break
            
        if not user_found:
            return False
            
        # Check against permission matrix
        allowed_actions = self.ROLE_PERMISSIONS.get(user_role, [])
        return action in allowed_actions

    def _is_system_admin(self, email: str) -> bool:
        """Check if user belongs to the platform's superadmin group."""
        system_admins_ref = self.db.collection("system_config").document("super_admins")
        doc = system_admins_ref.get()
        if doc.exists:
            admin_emails = doc.to_dict().get("emails", [])
            return email in admin_emails
        return False
        
    def assign_role(
        self,
        admin_email: str,
        target_email: str,
        customer_id: str,
        role: str
    ) -> Dict[str, Any]:
        """
        Assign a role to a user within a customer tenant.
        Only 'admin' role can assign roles.
        """
        if not self.check_permission(admin_email, customer_id, "manage_users"):
            raise PermissionError(f"User {admin_email} does not have permission to manage users.")
            
        if role not in self.ROLE_PERMISSIONS:
            raise ValueError(f"Invalid role '{role}'. Must be one of {list(self.ROLE_PERMISSIONS.keys())}")
            
        user_ref = self.db.collection(f"customers/{customer_id}/users").document(target_email)
        user_ref.set({
            "email": target_email,
            "role": role,
            "updatedAt": datetime.now(timezone.utc),
            "updatedBy": admin_email
        }, merge=True)
        
        return {"status": "success", "message": f"Role {role} assigned to {target_email}"}
