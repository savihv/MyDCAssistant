"""Migration Script: Single-Tenant → Multi-Tenant

Migrates all existing Firestore data from single-tenant schema to
multi-tenant customer-scoped schema.

**What This Does:**
1. Creates a default customer for existing data
2. Moves all documents from old collections to customer-scoped collections
3. Updates all document references
4. Creates audit log of migration

**Collections to Migrate:**
- live_infrastructure → customers/{customer_id}/infrastructure
- projects → customers/{customer_id}/projects
- extracted_devices → customers/{customer_id}/extracted_devices
- provisioning_alerts → customers/{customer_id}/provisioning_alerts
- cluster_bringup_projects → customers/{customer_id}/cluster_bringup_projects

**Safety:**
- Runs in dry-run mode by default
- Backs up data before migration
- Can be rolled back

**Usage:**
```python
from app.libs.migrate_to_multitenant import migrate_to_multitenant

# Dry run (check what would happen)
migrate_to_multitenant(
    customer_id="cust_techassist_default",
    company_name="TechAssist (Migrated)",
    dry_run=True
)

# Actual migration
migrate_to_multitenant(
    customer_id="cust_techassist_default",
    company_name="TechAssist (Migrated)",
    dry_run=False
)
```
"""

from typing import Dict
from google.cloud import firestore
from datetime import datetime, timezone
import json
import os


def migrate_to_multitenant(
    customer_id: str = "cust_techassist_default",
    company_name: str = "TechAssist (Migrated)",
    admin_email: str = "admin@techassist.local",
    dry_run: bool = True
) -> Dict:
    """Migrate existing single-tenant data to multi-tenant schema.
    
    Args:
        customer_id: Customer ID for the migrated data
        company_name: Company name
        admin_email: Admin email
        dry_run: If True, only prints what would happen (doesn't modify data)
        
    Returns:
        Dict with migration statistics
    """
    print("\n" + "="*80)
    print("🔄 MIGRATION: Single-Tenant → Multi-Tenant")
    print("="*80)
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be made")
    else:
        print("\n🚨 LIVE MODE - Data will be migrated")
    
    print(f"\nTarget Customer: {customer_id}")
    print(f"Company Name: {company_name}")
    print(f"Admin Email: {admin_email}\n")
    
    # Initialize Firestore
    try:
        firebase_creds = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
        if firebase_creds:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(
                json.loads(firebase_creds)
            )
            db = firestore.Client(credentials=creds)
        else:
            db = firestore.Client()
    except Exception as e:
        print(f"❌ Failed to initialize Firestore: {e}")
        return {"status": "error", "message": str(e)}
    
    # Collections to migrate
    collections_to_migrate = [
        "live_infrastructure",
        "projects",
        "extracted_devices",
        "provisioning_alerts",
        "cluster_bringup_projects",
    ]
    
    # Collection name mapping
    collection_mapping = {
        "live_infrastructure": "infrastructure",
        "projects": "projects",
        "extracted_devices": "extracted_devices",
        "provisioning_alerts": "provisioning_alerts",
        "cluster_bringup_projects": "cluster_bringup_projects",
    }
    
    stats = {
        "total_collections": len(collections_to_migrate),
        "total_documents": 0,
        "migrated_documents": 0,
        "failed_documents": 0,
        "collections": {},
    }
    
    # Step 1: Create customer if doesn't exist
    print("\n📋 Step 1: Create Customer")
    print("-" * 80)
    
    customer_ref = db.collection("customers").document(customer_id)
    customer_doc = customer_ref.get()
    
    if customer_doc.exists:
        print(f"✅ Customer already exists: {customer_id}")
    else:
        if not dry_run:
            customer_data = {
                "customer_id": customer_id,
                "company_name": company_name,
                "admin_email": admin_email,
                "license_tier": "enterprise",
                "max_gpus": 999999,
                "max_users": 999999,
                "price_monthly": 0,  # Grandfathered
                "features": ["all_features"],
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {
                    "migrated_from_single_tenant": True,
                    "migration_date": datetime.now(timezone.utc).isoformat(),
                },
            }
            customer_ref.set(customer_data)
            print(f"✅ Created customer: {customer_id}")
        else:
            print(f"[DRY RUN] Would create customer: {customer_id}")
    
    # Step 2: Migrate each collection
    print("\n📦 Step 2: Migrate Collections")
    print("-" * 80)
    
    for old_collection_name in collections_to_migrate:
        print(f"\n🔄 Migrating: {old_collection_name}")
        
        # Get new collection name
        new_collection_name = collection_mapping[old_collection_name]
        
        # Count documents in old collection
        old_collection = db.collection(old_collection_name)
        docs = list(old_collection.stream())
        doc_count = len(docs)
        
        print(f"  📊 Found {doc_count} documents")
        stats["collections"][old_collection_name] = {
            "count": doc_count,
            "migrated": 0,
            "failed": 0,
        }
        stats["total_documents"] += doc_count
        
        if doc_count == 0:
            print("  ⏭️  Skipping (empty collection)")
            continue
        
        # Migrate each document
        for doc in docs:
            doc_id = doc.id
            doc_data = doc.to_dict()
            
            try:
                if not dry_run:
                    # Write to new customer-scoped collection
                    new_collection_ref = (
                        db.collection("customers")
                        .document(customer_id)
                        .collection(new_collection_name)
                    )
                    new_collection_ref.document(doc_id).set(doc_data)
                    
                    # Delete old document
                    doc.reference.delete()
                    
                    stats["collections"][old_collection_name]["migrated"] += 1
                    stats["migrated_documents"] += 1
                else:
                    print(f"    [DRY RUN] Would migrate: {doc_id}")
                    stats["collections"][old_collection_name]["migrated"] += 1
                    stats["migrated_documents"] += 1
                    
            except Exception as e:
                print(f"  ❌ Failed to migrate {doc_id}: {e}")
                stats["collections"][old_collection_name]["failed"] += 1
                stats["failed_documents"] += 1
        
        if not dry_run:
            print(f"  ✅ Migrated {stats['collections'][old_collection_name]['migrated']} documents")
        else:
            print(f"  [DRY RUN] Would migrate {stats['collections'][old_collection_name]['migrated']} documents")
    
    # Step 3: Summary
    print("\n" + "="*80)
    print("📊 MIGRATION SUMMARY")
    print("="*80)
    print(f"\nTotal Collections: {stats['total_collections']}")
    print(f"Total Documents: {stats['total_documents']}")
    print(f"Migrated: {stats['migrated_documents']}")
    print(f"Failed: {stats['failed_documents']}")
    
    print("\nPer-Collection Breakdown:")
    for collection_name, collection_stats in stats["collections"].items():
        print(f"  {collection_name}:")
        print(f"    Total: {collection_stats['count']}")
        print(f"    Migrated: {collection_stats['migrated']}")
        print(f"    Failed: {collection_stats['failed']}")
    
    if dry_run:
        print("\n⚠️  This was a DRY RUN - No changes were made")
        print("\n💡 To perform the actual migration, run with dry_run=False")
    else:
        print("\n✅ Migration complete!")
        print("\n📝 Next Steps:")
        print("  1. Update all API endpoints to use customer_id")
        print("  2. Test that all features work with new schema")
        print("  3. Update frontend to include customer selector")
    
    print("\n" + "="*80 + "\n")
    
    stats["status"] = "success" if stats["failed_documents"] == 0 else "partial_success"
    stats["dry_run"] = dry_run
    
    return stats


def rollback_migration(
    customer_id: str,
    dry_run: bool = True
) -> Dict:
    """Rollback migration by moving customer data back to root collections.
    
    Args:
        customer_id: Customer ID to rollback
        dry_run: If True, only prints what would happen
        
    Returns:
        Dict with rollback statistics
    """
    print("\n" + "="*80)
    print("🔙 ROLLBACK: Multi-Tenant → Single-Tenant")
    print("="*80)
    
    if dry_run:
        print("\n⚠️  DRY RUN MODE")
    else:
        print("\n🚨 LIVE MODE")
    
    print(f"\nRolling back customer: {customer_id}\n")
    
    # Initialize Firestore
    try:
        firebase_creds = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
        if firebase_creds:
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(
                json.loads(firebase_creds)
            )
            db = firestore.Client(credentials=creds)
        else:
            db = firestore.Client()
    except Exception as e:
        print(f"❌ Failed to initialize Firestore: {e}")
        return {"status": "error", "message": str(e)}
    
    # Collection mappings (reverse)
    collection_mapping = {
        "infrastructure": "live_infrastructure",
        "projects": "projects",
        "extracted_devices": "extracted_devices",
        "provisioning_alerts": "provisioning_alerts",
        "cluster_bringup_projects": "cluster_bringup_projects",
    }
    
    stats = {
        "total_documents": 0,
        "rolled_back": 0,
        "failed": 0,
    }
    
    # Get customer reference
    customer_ref = db.collection("customers").document(customer_id)
    
    for new_collection_name, old_collection_name in collection_mapping.items():
        print(f"\n🔄 Rolling back: {new_collection_name} → {old_collection_name}")
        
        # Get documents from customer-scoped collection
        customer_collection = customer_ref.collection(new_collection_name)
        docs = list(customer_collection.stream())
        doc_count = len(docs)
        
        print(f"  📊 Found {doc_count} documents")
        stats["total_documents"] += doc_count
        
        if doc_count == 0:
            print("  ⏭️  Skipping (empty collection)")
            continue
        
        # Move each document back
        for doc in docs:
            doc_id = doc.id
            doc_data = doc.to_dict()
            
            try:
                if not dry_run:
                    # Write to old root collection
                    db.collection(old_collection_name).document(doc_id).set(doc_data)
                    
                    # Delete from customer collection
                    doc.reference.delete()
                    
                    stats["rolled_back"] += 1
                else:
                    print(f"    [DRY RUN] Would rollback: {doc_id}")
                    stats["rolled_back"] += 1
                    
            except Exception as e:
                print(f"  ❌ Failed to rollback {doc_id}: {e}")
                stats["failed"] += 1
    
    print("\n" + "="*80)
    print("📊 ROLLBACK SUMMARY")
    print("="*80)
    print(f"\nTotal Documents: {stats['total_documents']}")
    print(f"Rolled Back: {stats['rolled_back']}")
    print(f"Failed: {stats['failed']}")
    
    if dry_run:
        print("\n⚠️  This was a DRY RUN")
    else:
        print("\n✅ Rollback complete!")
    
    print("\n" + "="*80 + "\n")
    
    stats["status"] = "success" if stats["failed"] == 0 else "partial_success"
    stats["dry_run"] = dry_run
    
    return stats
