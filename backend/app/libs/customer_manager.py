"""Customer Management for Multi-Tenant SaaS

Manages enterprise customer accounts with complete data isolation.
Each customer gets their own namespace in Firestore.

**Firestore Schema:**
```
/customers/{customer_id}
  - company_name: "NVIDIA Corporation"
  - admin_email: "admin@nvidia.com"
  - license_tier: "enterprise" | "professional" | "starter"
  - created_at: "2026-02-16T..."
  - status: "active" | "suspended" | "trial"
  - max_gpus: 512  # License limit
  - metadata: {industry: "AI", employee_count: 10000}

/customers/{customer_id}/infrastructure/{device_id}
  - (all device data scoped to customer)

/customers/{customer_id}/projects/{project_id}
  - (all projects scoped to customer)

/customers/{customer_id}/users/{user_id}
  - (team members with roles)

/customers/{customer_id}/audit_logs/{log_id}
  - (activity audit trail)
```

**Usage:**
    from app.libs.customer_manager import CustomerManager
    
    manager = CustomerManager(db)
    customer = manager.create_customer(
        company_name="NVIDIA Corporation",
        admin_email="admin@nvidia.com",
        license_tier="enterprise"
    )
    
    print(f"Customer ID: {customer['customer_id']}")
"""

import re
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional, List
from google.cloud import firestore


class CustomerManager:
    """Manages customer accounts for multi-tenant SaaS platform."""
    
    # License tier limits
    LICENSE_TIERS = {
        "starter": {
            "max_gpus": 64,
            "max_users": 3,
            "price_monthly": 499,
            "features": ["basic_ztp", "lldp_validation", "cabling_matrix"]
        },
        "professional": {
            "max_gpus": 512,
            "max_users": 10,
            "price_monthly": 2499,
            "features": ["basic_ztp", "lldp_validation", "cabling_matrix", "export_terraform", "export_ansible", "api_access"]
        },
        "enterprise": {
            "max_gpus": 999999,  # Unlimited
            "max_users": 999999,  # Unlimited
            "price_monthly": 9999,
            "features": ["all_features", "sso", "audit_logs", "priority_support", "dedicated_support", "custom_templates"]
        }
    }
    
    def __init__(self, db_client: firestore.Client):
        """Initialize customer manager.
        
        Args:
            db_client: Firestore client instance
        """
        self.db = db_client
        print("✅ CustomerManager initialized")
    
    def create_customer(
        self,
        company_name: str,
        admin_email: str,
        license_tier: str = "starter",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Create a new customer account.
        
        Args:
            company_name: Company name (e.g., "NVIDIA Corporation")
            admin_email: Email of first admin user
            license_tier: "starter", "professional", or "enterprise"
            metadata: Optional metadata (industry, employee_count, etc.)
            
        Returns:
            Dict with customer data including customer_id
            
        Raises:
            ValueError: If license_tier invalid or customer already exists
        """
        # Validate license tier
        if license_tier not in self.LICENSE_TIERS:
            raise ValueError(f"Invalid license tier: {license_tier}. Must be one of {list(self.LICENSE_TIERS.keys())}")
        
        # Generate customer ID from company name
        customer_id = self._generate_customer_id(company_name)
        
        # Check if customer already exists
        existing = self.db.collection("customers").document(customer_id).get()
        if existing.exists:
            raise ValueError(f"Customer already exists: {customer_id}")
        
        # Get license tier limits
        tier_config = self.LICENSE_TIERS[license_tier]
        
        # Create customer document
        customer_data = {
            "customer_id": customer_id,
            "company_name": company_name,
            "admin_email": admin_email,
            "license_tier": license_tier,
            "max_gpus": tier_config["max_gpus"],
            "max_users": tier_config["max_users"],
            "price_monthly": tier_config["price_monthly"],
            "features": tier_config["features"],
            "status": "trial",  # Start in trial mode
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "trial_ends_at": self._calculate_trial_end(),
        }
        
        # Write to Firestore
        self.db.collection("customers").document(customer_id).set(customer_data)
        
        # Initialize customer namespace (create empty collections)
        self._initialize_customer_namespace(customer_id)
        
        # Add admin as first user
        self._add_initial_admin(customer_id, admin_email)
        
        print(f"✅ Created customer: {customer_id} ({company_name})")
        return customer_data
    
    def get_customer(self, customer_id: str) -> Optional[Dict]:
        """Get customer data by ID.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Customer data dict or None if not found
        """
        doc = self.db.collection("customers").document(customer_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    
    def list_customers(
        self,
        status: Optional[str] = None,
        license_tier: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """List all customers with optional filtering.
        
        Args:
            status: Filter by status ("active", "trial", "suspended")
            license_tier: Filter by tier ("starter", "professional", "enterprise")
            limit: Max results to return
            
        Returns:
            List of customer dicts
        """
        query = self.db.collection("customers")
        
        if status:
            query = query.where("status", "==", status)
        
        if license_tier:
            query = query.where("license_tier", "==", license_tier)
        
        query = query.limit(limit)
        
        customers = []
        for doc in query.stream():
            customers.append(doc.to_dict())
        
        return customers
    
    def update_customer(
        self,
        customer_id: str,
        updates: Dict
    ) -> Dict:
        """Update customer data.
        
        Args:
            customer_id: Customer ID
            updates: Dict of fields to update
            
        Returns:
            Updated customer data
            
        Raises:
            ValueError: If customer not found
        """
        doc_ref = self.db.collection("customers").document(customer_id)
        
        # Check if customer exists
        if not doc_ref.get().exists:
            raise ValueError(f"Customer not found: {customer_id}")
        
        # Add updated_at timestamp
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Update document
        doc_ref.update(updates)
        
        # Return updated data
        return doc_ref.get().to_dict()
    
    def upgrade_license(
        self,
        customer_id: str,
        new_tier: str
    ) -> Dict:
        """Upgrade customer's license tier.
        
        Args:
            customer_id: Customer ID
            new_tier: New tier ("professional" or "enterprise")
            
        Returns:
            Updated customer data
            
        Raises:
            ValueError: If tier invalid or downgrade attempted
        """
        if new_tier not in self.LICENSE_TIERS:
            raise ValueError(f"Invalid license tier: {new_tier}")
        
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer not found: {customer_id}")
        
        current_tier = customer["license_tier"]
        tier_order = ["starter", "professional", "enterprise"]
        
        if tier_order.index(new_tier) < tier_order.index(current_tier):
            raise ValueError(f"Cannot downgrade from {current_tier} to {new_tier}")
        
        # Get new tier config
        tier_config = self.LICENSE_TIERS[new_tier]
        
        # Update customer
        updates = {
            "license_tier": new_tier,
            "max_gpus": tier_config["max_gpus"],
            "max_users": tier_config["max_users"],
            "price_monthly": tier_config["price_monthly"],
            "features": tier_config["features"],
            "status": "active",  # Activate when upgrading
        }
        
        return self.update_customer(customer_id, updates)
    
    def suspend_customer(self, customer_id: str, reason: str = "") -> Dict:
        """Suspend a customer account (non-payment, violation, etc.).
        
        Args:
            customer_id: Customer ID
            reason: Reason for suspension
            
        Returns:
            Updated customer data
        """
        return self.update_customer(customer_id, {
            "status": "suspended",
            "suspension_reason": reason,
            "suspended_at": datetime.now(timezone.utc).isoformat()
        })
    
    def activate_customer(self, customer_id: str) -> Dict:
        """Activate a suspended customer.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Updated customer data
        """
        return self.update_customer(customer_id, {
            "status": "active",
            "suspension_reason": None,
            "suspended_at": None
        })
    
    def delete_customer(self, customer_id: str, confirm: bool = False) -> bool:
        """Delete a customer and ALL their data.
        
        ⚠️ WARNING: This is irreversible and deletes:
        - Customer account
        - All infrastructure data
        - All projects
        - All users
        - All audit logs
        
        Args:
            customer_id: Customer ID
            confirm: Must be True to actually delete
            
        Returns:
            True if deleted, False if not confirmed
        """
        if not confirm:
            print("⚠️ Delete not confirmed. Set confirm=True to actually delete.")
            return False
        
        # Delete customer document
        self.db.collection("customers").document(customer_id).delete()
        
        # Delete all subcollections (infrastructure, projects, users, audit_logs)
        self._delete_customer_namespace(customer_id)
        
        print(f"✅ Deleted customer: {customer_id}")
        return True
    
    def check_gpu_quota(self, customer_id: str) -> Dict:
        """Check GPU quota usage for customer.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Dict with max_gpus, used_gpus, remaining_gpus, quota_exceeded
        """
        customer = self.get_customer(customer_id)
        if not customer:
            raise ValueError(f"Customer not found: {customer_id}")
        
        # Count GPUs in customer's infrastructure
        infra_query = (
            self.db.collection("customers")
            .document(customer_id)
            .collection("infrastructure")
            .where("tier", "==", "COMPUTE")
        )
        
        gpu_count = 0
        for doc in infra_query.stream():
            device = doc.to_dict()
            # Assume 8 GPUs per DGX node (adjust based on actual device model)
            gpu_count += device.get("gpu_count", 8)
        
        max_gpus = customer["max_gpus"]
        remaining = max_gpus - gpu_count
        
        return {
            "max_gpus": max_gpus,
            "used_gpus": gpu_count,
            "remaining_gpus": max(0, remaining),
            "quota_exceeded": gpu_count > max_gpus,
            "license_tier": customer["license_tier"]
        }
    
    def _generate_customer_id(self, company_name: str) -> str:
        """Generate unique customer ID from company name.
        
        Examples:
            "NVIDIA Corporation" -> "cust_nvidia_corporation"
            "Acme Inc." -> "cust_acme_inc"
        
        Args:
            company_name: Company name
            
        Returns:
            Unique customer ID
        """
        # Convert to lowercase, replace spaces/special chars with underscores
        slug = re.sub(r'[^a-z0-9]+', '_', company_name.lower())
        slug = slug.strip('_')
        
        # Truncate to 40 chars
        slug = slug[:40]
        
        # Add prefix
        customer_id = f"cust_{slug}"
        
        # Add random suffix if collision (check Firestore)
        while self.db.collection("customers").document(customer_id).get().exists:
            suffix = secrets.token_hex(3)  # 6 chars
            customer_id = f"cust_{slug}_{suffix}"
        
        return customer_id
    
    def _calculate_trial_end(self, days: int = 30) -> str:
        """Calculate trial end date (30 days from now).
        
        Args:
            days: Trial duration in days
            
        Returns:
            ISO 8601 timestamp
        """
        from datetime import timedelta
        end_date = datetime.now(timezone.utc) + timedelta(days=days)
        return end_date.isoformat()
    
    def _initialize_customer_namespace(self, customer_id: str):
        """Create empty collections for new customer.
        
        Args:
            customer_id: Customer ID
        """
        # Firestore creates collections on first document write
        # Write placeholder docs then delete (to initialize collections)
        customer_ref = self.db.collection("customers").document(customer_id)
        
        # Initialize infrastructure collection
        infra_ref = customer_ref.collection("infrastructure").document("_init")
        infra_ref.set({"_placeholder": True})
        infra_ref.delete()
        
        # Initialize projects collection
        projects_ref = customer_ref.collection("projects").document("_init")
        projects_ref.set({"_placeholder": True})
        projects_ref.delete()
        
        # Initialize users collection
        users_ref = customer_ref.collection("users").document("_init")
        users_ref.set({"_placeholder": True})
        users_ref.delete()
        
        # Initialize audit_logs collection
        logs_ref = customer_ref.collection("audit_logs").document("_init")
        logs_ref.set({"_placeholder": True})
        logs_ref.delete()
        
        print(f"  ✅ Initialized namespace for {customer_id}")
    
    def _add_initial_admin(self, customer_id: str, admin_email: str):
        """Add first admin user to customer.
        
        Args:
            customer_id: Customer ID
            admin_email: Admin email
        """
        user_data = {
            "email": admin_email,
            "role": "admin",
            "invited_by": "system",
            "invited_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None,
            "status": "active"
        }
        
        # Use email as document ID (sanitized)
        user_id = re.sub(r'[^a-z0-9]+', '_', admin_email.lower())
        
        self.db.collection("customers").document(customer_id).collection("users").document(user_id).set(user_data)
        
        print(f"  ✅ Added admin user: {admin_email}")
    
    def _delete_customer_namespace(self, customer_id: str):
        """Delete all subcollections for a customer.
        
        Args:
            customer_id: Customer ID
        """
        customer_ref = self.db.collection("customers").document(customer_id)
        
        # Delete infrastructure
        self._delete_collection(customer_ref.collection("infrastructure"))
        
        # Delete projects
        self._delete_collection(customer_ref.collection("projects"))
        
        # Delete users
        self._delete_collection(customer_ref.collection("users"))
        
        # Delete audit logs
        self._delete_collection(customer_ref.collection("audit_logs"))
        
        print(f"  ✅ Deleted all data for {customer_id}")
    
    def _delete_collection(self, collection_ref, batch_size: int = 100):
        """Delete all documents in a collection.
        
        Args:
            collection_ref: Firestore collection reference
            batch_size: Batch size for deletion
        """
        docs = collection_ref.limit(batch_size).stream()
        deleted = 0
        
        for doc in docs:
            doc.reference.delete()
            deleted += 1
        
        if deleted >= batch_size:
            # More documents to delete
            return self._delete_collection(collection_ref, batch_size)
