"""Customer Management API

RESTful API for managing customer accounts in the multi-tenant SaaS platform.

**Endpoints:**

1. POST /customers - Create new customer
2. GET /customers/{customer_id} - Get customer details
3. GET /customers - List all customers (admin only)
4. PUT /customers/{customer_id} - Update customer
5. POST /customers/{customer_id}/upgrade - Upgrade license tier
6. POST /customers/{customer_id}/suspend - Suspend customer
7. POST /customers/{customer_id}/activate - Activate customer
8. DELETE /customers/{customer_id} - Delete customer (irreversible)
9. GET /customers/{customer_id}/quota - Check GPU quota usage

**Authentication:**
All endpoints except POST /customers require authentication.
Platform admin endpoints (list all customers) require special admin role.

**Customer Lifecycle:**
1. Create customer → status="trial"
2. Customer upgrades → status="active"
3. Payment fails → status="suspended"
4. Customer pays → status="active"
5. Customer churns → DELETE (data purged after 30 days)
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict
from app.libs.customer_manager import CustomerManager
from google.cloud import firestore
import os
import json

router = APIRouter()

# Initialize Firestore and CustomerManager
try:
    firebase_creds = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
    if firebase_creds:
        creds = json.loads(firebase_creds)
        db = firestore.Client.from_service_account_info(creds)
    else:
        db = firestore.Client()
    
    customer_manager = CustomerManager(db)
except Exception as e:
    print(f"⚠️ Warning: Could not initialize CustomerManager: {e}")
    customer_manager = None
    db = None


# ============================================================================
# Request/Response Models
# ============================================================================

class CreateCustomerRequest(BaseModel):
    """Request to create a new customer."""
    company_name: str
    admin_email: EmailStr
    license_tier: str = "starter"  # "starter", "professional", "enterprise"
    metadata: Optional[Dict] = None


class UpdateCustomerRequest(BaseModel):
    """Request to update customer data."""
    company_name: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict] = None


class UpgradeLicenseRequest(BaseModel):
    """Request to upgrade license tier."""
    new_tier: str  # "professional" or "enterprise"


class SuspendCustomerRequest(BaseModel):
    """Request to suspend customer."""
    reason: str = "Payment failure"


class CustomerResponse(BaseModel):
    """Customer data response."""
    customer_id: str
    company_name: str
    admin_email: str
    license_tier: str
    max_gpus: int
    max_users: int
    price_monthly: int
    features: List[str]
    status: str
    created_at: str
    updated_at: str
    metadata: Dict
    trial_ends_at: Optional[str] = None


class QuotaResponse(BaseModel):
    """GPU quota usage response."""
    max_gpus: int
    used_gpus: int
    remaining_gpus: int
    quota_exceeded: bool
    license_tier: str


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/customers", response_model=CustomerResponse)
def create_customer(request: CreateCustomerRequest) -> CustomerResponse:
    """Create a new customer account.
    
    This is the entry point for new customer signups.
    Creates isolated namespace in Firestore and sets up admin user.
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8000/customer-management/customers \
      -H "Content-Type: application/json" \
      -d '{
        "company_name": "NVIDIA Corporation",
        "admin_email": "admin@nvidia.com",
        "license_tier": "enterprise",
        "metadata": {"industry": "AI", "employee_count": 10000}
      }'
    ```
    
    Args:
        request: CreateCustomerRequest
        
    Returns:
        CustomerResponse with customer_id
        
    Raises:
        HTTPException 400: If license_tier invalid or customer exists
        HTTPException 500: If CustomerManager not initialized
    """
    if not customer_manager:
        raise HTTPException(
            status_code=500,
            detail="CustomerManager not initialized. Check Firestore configuration."
        )
    
    try:
        customer_data = customer_manager.create_customer(
            company_name=request.company_name,
            admin_email=request.admin_email,
            license_tier=request.license_tier,
            metadata=request.metadata
        )
        
        return CustomerResponse(**customer_data)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create customer: {str(e)}")


@router.get("/customers/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    x_customer_id: Optional[str] = Header(None)
) -> CustomerResponse:
    """Get customer details by ID.
    
    **Security:** Users can only access their own customer data.
    Platform admins can access any customer.
    
    Args:
        customer_id: Customer ID
        x_customer_id: Customer ID from header (for auth check)
        
    Returns:
        CustomerResponse
        
    Raises:
        HTTPException 403: If trying to access another customer's data
        HTTPException 404: If customer not found
    """
    if not customer_manager:
        raise HTTPException(status_code=500, detail="CustomerManager not initialized.")
    
    # Security check: ensure user can only access their own customer data
    # (unless platform admin - TODO: implement platform admin check)
    if x_customer_id and x_customer_id != customer_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied. You can only access your own customer data."
        )
    
    customer_data = customer_manager.get_customer(customer_id)
    
    if not customer_data:
        raise HTTPException(
            status_code=404,
            detail=f"Customer not found: {customer_id}"
        )
    
    return CustomerResponse(**customer_data)


@router.get("/customers", response_model=List[CustomerResponse])
def list_customers(
    status: Optional[str] = None,
    license_tier: Optional[str] = None,
    limit: int = 100,
    x_platform_admin: Optional[str] = Header(None)
) -> List[CustomerResponse]:
    """List all customers.
    
    **Security:** Platform admin only.
    This endpoint is for internal operations team, not customer-facing.
    
    Args:
        status: Filter by status ("active", "trial", "suspended")
        license_tier: Filter by tier ("starter", "professional", "enterprise")
        limit: Max results (default 100)
        x_platform_admin: Admin auth token
        
    Returns:
        List of CustomerResponse
        
    Raises:
        HTTPException 403: If not platform admin
    """
    # TODO: Implement proper platform admin authentication
    # For now, require X-Platform-Admin header
    if not x_platform_admin:
        raise HTTPException(
            status_code=403,
            detail="Platform admin access required. This endpoint is for internal use only."
        )
    
    if not customer_manager:
        raise HTTPException(status_code=500, detail="CustomerManager not initialized.")
    
    customers = customer_manager.list_customers(
        status=status,
        license_tier=license_tier,
        limit=limit
    )
    
    return [CustomerResponse(**c) for c in customers]


@router.put("/customers/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    request: UpdateCustomerRequest,
    x_customer_id: Optional[str] = Header(None)
) -> CustomerResponse:
    """Update customer data.
    
    **Allowed updates:**
    - company_name (if legal name changes)
    - metadata (industry, employee_count, etc.)
    - status (admin only - use suspend/activate endpoints instead)
    
    Args:
        customer_id: Customer ID
        request: UpdateCustomerRequest
        x_customer_id: Customer ID from header (for auth check)
        
    Returns:
        Updated CustomerResponse
        
    Raises:
        HTTPException 403: If unauthorized
        HTTPException 404: If customer not found
    """
    if not customer_manager:
        raise HTTPException(status_code=500, detail="CustomerManager not initialized.")
    
    # Security check
    if x_customer_id and x_customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    
    # Build updates dict (only include provided fields)
    updates = {}
    if request.company_name:
        updates["company_name"] = request.company_name
    if request.metadata:
        updates["metadata"] = request.metadata
    if request.status:
        updates["status"] = request.status
    
    try:
        updated_customer = customer_manager.update_customer(customer_id, updates)
        return CustomerResponse(**updated_customer)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")


@router.post("/customers/{customer_id}/upgrade", response_model=CustomerResponse)
def upgrade_license(
    customer_id: str,
    request: UpgradeLicenseRequest,
    x_customer_id: Optional[str] = Header(None)
) -> CustomerResponse:
    """Upgrade customer's license tier.
    
    **Upgrade paths:**
    - starter → professional
    - starter → enterprise
    - professional → enterprise
    
    Downgrades are not allowed (contact support for special cases).
    
    Args:
        customer_id: Customer ID
        request: UpgradeLicenseRequest
        x_customer_id: Customer ID from header (for auth check)
        
    Returns:
        Updated CustomerResponse
        
    Raises:
        HTTPException 400: If downgrade attempted or invalid tier
        HTTPException 403: If unauthorized
    """
    if not customer_manager:
        raise HTTPException(status_code=500, detail="CustomerManager not initialized.")
    
    # Security check
    if x_customer_id and x_customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    
    try:
        upgraded_customer = customer_manager.upgrade_license(customer_id, request.new_tier)
        return CustomerResponse(**upgraded_customer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upgrade failed: {str(e)}")


@router.post("/customers/{customer_id}/suspend")
def suspend_customer(
    customer_id: str,
    request: SuspendCustomerRequest,
    x_platform_admin: Optional[str] = Header(None)
) -> Dict:
    """Suspend a customer account.
    
    **Platform admin only.**
    
    Suspended customers:
    - Cannot log in
    - Cannot access any features
    - Data is retained (not deleted)
    - Can be reactivated
    
    Common reasons: Payment failure, policy violation, security breach.
    
    Args:
        customer_id: Customer ID
        request: SuspendCustomerRequest
        x_platform_admin: Admin auth token
        
    Returns:
        Success message
        
    Raises:
        HTTPException 403: If not platform admin
    """
    if not x_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin access required.")
    
    if not customer_manager:
        raise HTTPException(status_code=500, detail="CustomerManager not initialized.")
    
    try:
        customer_manager.suspend_customer(customer_id, request.reason)
        return {
            "status": "success",
            "message": f"Customer {customer_id} suspended",
            "reason": request.reason
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suspension failed: {str(e)}")


@router.post("/customers/{customer_id}/activate")
def activate_customer(
    customer_id: str,
    x_platform_admin: Optional[str] = Header(None)
) -> Dict:
    """Activate a suspended customer.
    
    **Platform admin only.**
    
    Args:
        customer_id: Customer ID
        x_platform_admin: Admin auth token
        
    Returns:
        Success message
        
    Raises:
        HTTPException 403: If not platform admin
    """
    if not x_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin access required.")
    
    if not customer_manager:
        raise HTTPException(status_code=500, detail="CustomerManager not initialized.")
    
    try:
        customer_manager.activate_customer(customer_id)
        return {
            "status": "success",
            "message": f"Customer {customer_id} activated"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Activation failed: {str(e)}")


@router.delete("/customers/{customer_id}")
def delete_customer(
    customer_id: str,
    confirm: bool = False,
    x_platform_admin: Optional[str] = Header(None)
) -> Dict:
    """Delete a customer and ALL their data.
    
    ⚠️ **IRREVERSIBLE OPERATION**
    
    **Platform admin only.**
    
    Deletes:
    - Customer account
    - All infrastructure data
    - All projects
    - All users
    - All audit logs
    
    Use case: Customer requests data deletion (GDPR right to be forgotten).
    
    Args:
        customer_id: Customer ID
        confirm: Must be True to actually delete
        x_platform_admin: Admin auth token
        
    Returns:
        Success message
        
    Raises:
        HTTPException 403: If not platform admin
        HTTPException 400: If confirm not True
    """
    if not x_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin access required.")
    
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Must set confirm=true query parameter to delete customer. This is irreversible."
        )
    
    if not customer_manager:
        raise HTTPException(status_code=500, detail="CustomerManager not initialized.")
    
    try:
        deleted = customer_manager.delete_customer(customer_id, confirm=True)
        
        if deleted:
            return {
                "status": "success",
                "message": f"Customer {customer_id} permanently deleted"
            }
        else:
            return {
                "status": "failed",
                "message": "Deletion not confirmed"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.get("/customers/{customer_id}/quota", response_model=QuotaResponse)
def check_quota(
    customer_id: str,
    x_customer_id: Optional[str] = Header(None)
) -> QuotaResponse:
    """Check GPU quota usage for customer.
    
    Returns current GPU count vs license limit.
    Used to enforce quota and prompt upgrades.
    
    Args:
        customer_id: Customer ID
        x_customer_id: Customer ID from header (for auth check)
        
    Returns:
        QuotaResponse
        
    Raises:
        HTTPException 403: If unauthorized
        HTTPException 404: If customer not found
    """
    if not customer_manager:
        raise HTTPException(status_code=500, detail="CustomerManager not initialized.")
    
    # Security check
    if x_customer_id and x_customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    
    try:
        quota_data = customer_manager.check_gpu_quota(customer_id)
        return QuotaResponse(**quota_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Quota check failed: {str(e)}")
