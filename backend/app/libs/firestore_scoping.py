"""Firestore Collection Scoping Utility

Provides helper functions to automatically scope Firestore queries by customer_id.
Ensures all database operations are isolated to the correct customer namespace.

**Migration Path:**

OLD (single-tenant):
```python
db.collection("live_infrastructure").where("projectId", "==", project_id).stream()
```

NEW (multi-tenant):
```python
from app.libs.firestore_scoping import get_scoped_collection

get_scoped_collection(db, customer_id, "infrastructure").where("projectId", "==", project_id).stream()
```

**Schema Migration:**
- `/live_infrastructure/{doc_id}` → `/customers/{customer_id}/infrastructure/{doc_id}`
- `/projects/{project_id}` → `/customers/{customer_id}/projects/{project_id}`
- `/extracted_devices/{doc_id}` → `/customers/{customer_id}/extracted_devices/{doc_id}`
- `/provisioning_alerts/{alert_id}` → `/customers/{customer_id}/provisioning_alerts/{alert_id}`
- `/cluster_bringup_projects/{project_id}` → `/customers/{customer_id}/cluster_bringup_projects/{project_id}`
"""

from typing import Optional
from google.cloud import firestore


# Collection name mapping: old name → new name (scoped under customer)
COLLECTION_MAPPING = {
    "live_infrastructure": "infrastructure",  # Rename for clarity
    "projects": "projects",  # Keep same name
    "extracted_devices": "extracted_devices",
    "provisioning_alerts": "provisioning_alerts",
    "cluster_bringup_projects": "cluster_bringup_projects",
    "audit_logs": "audit_logs",
    "users": "users",
}


def get_scoped_collection(
    db: firestore.Client,
    customer_id: str,
    collection_name: str
) -> firestore.CollectionReference:
    """Get a Firestore collection scoped to a customer.
    
    Args:
        db: Firestore client
        customer_id: Customer ID (e.g., "cust_nvidia_corporation")
        collection_name: Collection name (use old name, it will be mapped)
        
    Returns:
        CollectionReference scoped to customer namespace
        
    Example:
        # Get customer's infrastructure collection
        collection = get_scoped_collection(db, "cust_nvidia", "live_infrastructure")
        devices = collection.where("tier", "==", "COMPUTE").stream()
    """
    # Map old collection name to new name
    scoped_name = COLLECTION_MAPPING.get(collection_name, collection_name)
    
    # Return customer-scoped collection
    return (
        db.collection("customers")
        .document(customer_id)
        .collection(scoped_name)
    )


def get_customer_document(
    db: firestore.Client,
    customer_id: str
) -> firestore.DocumentReference:
    """Get the customer document reference.
    
    Args:
        db: Firestore client
        customer_id: Customer ID
        
    Returns:
        DocumentReference for customer
    """
    return db.collection("customers").document(customer_id)


def migrate_document_to_customer(
    db: firestore.Client,
    customer_id: str,
    old_collection: str,
    doc_id: str
) -> bool:
    """Migrate a single document from old schema to customer-scoped schema.
    
    Args:
        db: Firestore client
        customer_id: Customer ID
        old_collection: Old collection name (e.g., "live_infrastructure")
        doc_id: Document ID to migrate
        
    Returns:
        True if migrated successfully, False if document not found
        
    Example:
        migrate_document_to_customer(
            db,
            "cust_nvidia",
            "live_infrastructure",
            "device_SU1-L3-P0"
        )
    """
    # Get document from old collection
    old_ref = db.collection(old_collection).document(doc_id)
    old_doc = old_ref.get()
    
    if not old_doc.exists:
        print(f"⚠️ Document not found: {old_collection}/{doc_id}")
        return False
    
    # Get data
    data = old_doc.to_dict()
    
    # Write to new customer-scoped collection
    new_collection = get_scoped_collection(db, customer_id, old_collection)
    new_collection.document(doc_id).set(data)
    
    print(f"✅ Migrated {old_collection}/{doc_id} → customers/{customer_id}/{COLLECTION_MAPPING[old_collection]}/{doc_id}")
    
    # Delete old document
    old_ref.delete()
    
    return True


def migrate_collection_to_customer(
    db: firestore.Client,
    customer_id: str,
    collection_name: str,
    batch_size: int = 100
) -> int:
    """Migrate an entire collection to customer-scoped schema.
    
    Args:
        db: Firestore client
        customer_id: Customer ID
        collection_name: Collection to migrate
        batch_size: Number of documents per batch
        
    Returns:
        Number of documents migrated
        
    Example:
        count = migrate_collection_to_customer(
            db,
            "cust_nvidia",
            "live_infrastructure"
        )
        print(f"Migrated {count} devices")
    """
    print(f"\n🔄 Migrating {collection_name} to customer {customer_id}...")
    
    migrated_count = 0
    
    # Get all documents from old collection
    old_collection = db.collection(collection_name)
    docs = old_collection.limit(batch_size).stream()
    
    for doc in docs:
        # Get data
        data = doc.to_dict()
        doc_id = doc.id
        
        # Write to new customer-scoped collection
        new_collection = get_scoped_collection(db, customer_id, collection_name)
        new_collection.document(doc_id).set(data)
        
        # Delete old document
        doc.reference.delete()
        
        migrated_count += 1
        
        if migrated_count % 10 == 0:
            print(f"  ✅ Migrated {migrated_count} documents...")
    
    print(f"\n✅ Migration complete: {migrated_count} documents migrated")
    return migrated_count


def get_legacy_collection(
    db: firestore.Client,
    collection_name: str,
    customer_id: Optional[str] = None
) -> firestore.CollectionReference:
    """Get collection - uses scoped version if customer_id provided, otherwise legacy.
    
    This function helps during migration period where some code might not have
    customer_id yet.
    
    Args:
        db: Firestore client
        collection_name: Collection name
        customer_id: Customer ID (if None, uses legacy collection)
        
    Returns:
        CollectionReference
        
    Example:
        # During migration, this allows gradual rollout
        collection = get_legacy_collection(db, "live_infrastructure", customer_id)
    """
    if customer_id:
        return get_scoped_collection(db, customer_id, collection_name)
    else:
        # Legacy single-tenant collection
        print(f"⚠️ Using legacy collection {collection_name} without customer scoping")
        return db.collection(collection_name)


def ensure_customer_exists(
    db: firestore.Client,
    customer_id: str,
    company_name: str = "Unknown Customer"
) -> bool:
    """Ensure customer document exists. Creates if not found.
    
    Args:
        db: Firestore client
        customer_id: Customer ID
        company_name: Company name (for display)
        
    Returns:
        True if created, False if already exists
    """
    customer_ref = db.collection("customers").document(customer_id)
    customer_doc = customer_ref.get()
    
    if customer_doc.exists:
        return False
    
    # Create placeholder customer
    from datetime import datetime, timezone
    customer_ref.set({
        "customer_id": customer_id,
        "company_name": company_name,
        "license_tier": "enterprise",  # Default to enterprise for migrations
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "migrated": True,
    })
    
    print(f"✅ Created customer: {customer_id}")
    return True
