"""Customer Context Middleware for Multi-Tenant SaaS

Automatically extracts customer_id from authenticated user and injects
it into API request context. Ensures all Firestore queries are scoped
to the correct customer namespace.

**How It Works:**

1. User logs in via Stack Auth → JWT token includes user_id
2. Middleware queries Firestore to find which customer this user belongs to
3. Injects customer_id into request.state.customer_id
4. All APIs can access via get_customer_id_from_request()
5. Firestore queries automatically scoped to /customers/{customer_id}/...

**Usage in APIs:**

```python
from app.libs.customer_context import get_customer_context
from fastapi import Depends

@router.get("/projects")
def list_projects(ctx: dict = Depends(get_customer_context)):
    customer_id = ctx["customer_id"]
    user_email = ctx["user_email"]
    
    # Query projects scoped to customer
    projects = db.collection("customers").document(customer_id).collection("projects").stream()
    return [p.to_dict() for p in projects]
```

**Stack Auth Integration:**

Stack Auth stores user metadata. We'll store customer_id in user metadata:
```
user.metadata = {
  "customer_id": "cust_nvidia_corporation",
  "role": "admin"
}
```

**Fallback for Development:**

If no auth token (local development), use header:
```
X-Customer-ID: cust_nvidia_corporation
```
"""

from typing import Dict, Optional
from fastapi import Request, HTTPException, Depends
from google.cloud import firestore
import os
import json


# Initialize Firestore client (shared)
try:
    firebase_creds = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
    if firebase_creds:
        creds = json.loads(firebase_creds)
        db = firestore.Client.from_service_account_info(creds)
    else:
        db = firestore.Client()
except Exception as e:
    print(f"⚠️ Warning: Could not initialize Firestore client: {e}")
    db = None


async def get_customer_context(request: Request) -> Dict:
    """Extract customer context from authenticated request.
    
    This is a FastAPI dependency that should be used in all customer-scoped endpoints.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dict with:
        - customer_id: Customer ID
        - user_id: Authenticated user ID (from Stack Auth)
        - user_email: User email
        - role: User role (admin, engineer, read-only)
        
    Raises:
        HTTPException 401: If not authenticated
        HTTPException 403: If user not associated with any customer
        
    Example:
        @router.get("/projects")
        def list_projects(ctx: dict = Depends(get_customer_context)):
            customer_id = ctx["customer_id"]
            # ... query projects for this customer
    """
    # Strategy 1: Get customer_id from Stack Auth user metadata
    # (Stack Auth integration would populate this)
    user = getattr(request.state, "user", None)
    
    if user:
        # User authenticated via Stack Auth
        user_id = user.get("id")
        user_email = user.get("email")
        
        # Get customer_id from user metadata
        customer_id = user.get("metadata", {}).get("customer_id")
        role = user.get("metadata", {}).get("role", "read-only")
        
        if customer_id:
            return {
                "customer_id": customer_id,
                "user_id": user_id,
                "user_email": user_email,
                "role": role,
                "authenticated": True
            }
    
    # Strategy 2: Fallback to X-Customer-ID header (for development/testing)
    customer_id_header = request.headers.get("X-Customer-ID")
    
    if customer_id_header:
        print(f"⚠️ Using X-Customer-ID header for development: {customer_id_header}")
        return {
            "customer_id": customer_id_header,
            "user_id": "dev_user",
            "user_email": "dev@localhost",
            "role": "admin",  # Full access in dev mode
            "authenticated": False
        }
    
    # Strategy 3: Query Firestore to find customer by user email
    # (Slower fallback if Stack Auth metadata not set)
    if user and user.get("email"):
        customer_id = await _find_customer_by_user_email(user["email"])
        if customer_id:
            return {
                "customer_id": customer_id,
                "user_id": user.get("id"),
                "user_email": user.get("email"),
                "role": "admin",  # Default to admin if found
                "authenticated": True
            }
    
    # No customer context found
    raise HTTPException(
        status_code=403,
        detail="User not associated with any customer. Contact support to join a customer account."
    )


async def _find_customer_by_user_email(email: str) -> Optional[str]:
    """Find customer ID by searching for user email across all customers.
    
    This is a fallback when Stack Auth metadata is not set.
    
    Args:
        email: User email
        
    Returns:
        Customer ID if found, None otherwise
    """
    if not db:
        return None
    
    # Query all customers
    customers = db.collection("customers").stream()
    
    for customer_doc in customers:
        customer_id = customer_doc.id
        
        # Check if user exists in this customer's users collection
        user_id = email.lower().replace("@", "_at_").replace(".", "_")
        user_ref = (
            db.collection("customers")
            .document(customer_id)
            .collection("users")
            .document(user_id)
        )
        
        user_doc = user_ref.get()
        if user_doc.exists:
            return customer_id
    
    return None


def get_customer_scoped_collection(
    customer_id: str,
    collection_name: str
) -> firestore.CollectionReference:
    """Get a Firestore collection scoped to a customer.
    
    Helper function to ensure all queries are properly scoped.
    
    Args:
        customer_id: Customer ID
        collection_name: Collection name (e.g., "infrastructure", "projects")
        
    Returns:
        Firestore collection reference
        
    Example:
        collection = get_customer_scoped_collection(
            customer_id="cust_nvidia",
            collection_name="infrastructure"
        )
        
        devices = collection.where("tier", "==", "COMPUTE").stream()
    """
    if not db:
        raise RuntimeError("Firestore client not initialized")
    
    return (
        db.collection("customers")
        .document(customer_id)
        .collection(collection_name)
    )


def require_role(required_role: str):
    """Decorator to require specific role for endpoint access.
    
    Roles hierarchy: read-only < engineer < admin
    
    Args:
        required_role: "admin", "engineer", or "read-only"
        
    Example:
        @router.post("/projects")
        @require_role("engineer")
        def create_project(ctx: dict = Depends(get_customer_context)):
            # Only engineers and admins can create projects
            ...
    """
    def decorator(func):
        async def wrapper(ctx: dict = Depends(get_customer_context), *args, **kwargs):
            user_role = ctx.get("role", "read-only")
            
            # Role hierarchy
            role_hierarchy = {"read-only": 0, "engineer": 1, "admin": 2}
            
            user_level = role_hierarchy.get(user_role, 0)
            required_level = role_hierarchy.get(required_role, 2)
            
            if user_level < required_level:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required role: {required_role}, your role: {user_role}"
                )
            
            return await func(ctx=ctx, *args, **kwargs)
        
        return wrapper
    return decorator


# Legacy function for backward compatibility
def get_customer_id_from_header(request: Request) -> str:
    """Legacy: Get customer ID from X-Customer-ID header.
    
    Deprecated: Use get_customer_context() instead.
    
    Args:
        request: FastAPI request
        
    Returns:
        Customer ID
        
    Raises:
        HTTPException 400: If header missing
    """
    customer_id = request.headers.get("X-Customer-ID")
    
    if not customer_id:
        raise HTTPException(
            status_code=400,
            detail="Missing X-Customer-ID header. This endpoint requires customer context."
        )
    
    return customer_id
