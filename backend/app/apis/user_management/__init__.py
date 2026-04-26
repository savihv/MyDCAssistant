from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request, Body, BackgroundTasks, Query # Added Query
from app.auth import AuthorizedUser
from app.env import Mode, mode
import firebase_admin
from firebase_admin import auth, credentials, firestore
import databutton as db
from datetime import datetime, timezone # Added timezone
import json
import os

# Use centralized lazy Firebase initialization
from app.libs.firebase_config import get_firestore_client

# Helper function for parsing Firestore timestamps or dict representations
def parse_firestore_timestamp(ts_data: Any) -> Optional[datetime]:
    if not ts_data: return None
    if isinstance(ts_data, datetime): # Already a datetime object
        # Ensure it's offset-aware (UTC)
        if ts_data.tzinfo is None or ts_data.tzinfo.utcoffset(ts_data) is None:
            return ts_data.replace(tzinfo=timezone.utc)
        return ts_data
    if hasattr(ts_data, 'seconds') and hasattr(ts_data, 'nanoseconds'): # Firestore Timestamp object
        return datetime.fromtimestamp(ts_data.seconds + ts_data.nanoseconds / 1e9, tz=timezone.utc)
    if isinstance(ts_data, (int, float)): # Unix timestamp (seconds)
        return datetime.fromtimestamp(ts_data, tz=timezone.utc)
    if isinstance(ts_data, dict) and 'seconds' in ts_data: # Dict format from old UserData
         return datetime.fromtimestamp(ts_data['seconds'] + ts_data.get('nanoseconds', 0) / 1e9, tz=timezone.utc)
    return None


router = APIRouter()

# Models for user management
class PendingUser(BaseModel):
    id: str = Field(..., description="Firestore document ID for this request")
    uid: str = Field(..., description="User ID in Firebase Auth (same as document ID)")
    userEmail: str
    displayName: str
    requestedRole: str
    company: Optional[str] = None
    requestedAt: Optional[Dict[str, int]] = None
    status: str
    reviewedBy: Optional[str] = None
    reviewedAt: Optional[Dict[str, int]] = None
    rejectionReason: Optional[str] = None

class UserData(BaseModel):
    id: str
    uid: str
    email: str # from Firestore 'email'
    displayName: Optional[str] = None
    role: Optional[str] = None 
    company: Optional[str] = None
    
    # Status fields
    status: Optional[str] = None # e.g., "active", "inactive"
    approvalStatus: Optional[str] = None # e.g., "approved", "rejected"

    # Domain assignment
    assignedDomain: Optional[str] = None

    # Timestamps
    createdAt: Optional[datetime] = None
    lastActive: Optional[datetime] = None
    approvedAt: Optional[datetime] = None
    rejectedAt: Optional[datetime] = None

    # Actor UIDs
    approvedBy: Optional[str] = None
    rejectedBy: Optional[str] = None
    rejectionReason: Optional[str] = None
    photoURL: Optional[str] = None

class PendingUserListResponse(BaseModel):
    """Response model for pending user requests.
    Note: The 'id' and 'uid' fields should be identical - both contain the Firebase Auth user ID.
    """
    users: List[PendingUser]
    total: int

class UserListResponse(BaseModel):
    users: List[UserData]
    total: int

class ApproveRejectRequest(BaseModel):
    userId: str = Field(..., description="Document ID of the pending request to approve/reject")
    approve: bool
    rejectionReason: Optional[str] = None
    role: Optional[str] = Field(None, description="Role to assign to the user (technician or company_admin)")

class ApproveRejectResponse(BaseModel):
    success: bool
    message: str
    userId: str

class AssignDomainRequest(BaseModel):
    userId: str = Field(..., description="User ID to assign domain to")
    domain: str = Field(..., description="Domain key to assign (must be one of the valid domains)")

class AssignDomainResponse(BaseModel):
    success: bool
    message: str
    userId: str
    assignedDomain: str

class DomainListResponse(BaseModel):
    domains: Dict[str, str]

# Helper function to send email notifications for approval/rejection
def send_approval_notification(user_email: str, user_name: str, role: str, company: Optional[str] = None):
    subject = "Your TechTalk Account Has Been Approved"
    
    # Create the message based on the role
    if role == "company_admin":
        content_text = f"""Hello {user_name},

Your request for a Company Admin account at TechTalk has been approved!

You now have access to:
- Upload company-specific documents to the knowledge base
- Manage technicians in your company
- View analytics and usage statistics

You can log in now at: https://juniortechbot.riff.works/techassist

Thank you for choosing TechTalk.

Best regards,
The TechTalk Team
"""
    else:  # technician
        company_line = f"for {company}" if company else ""
        content_text = f"""Hello {user_name},

Your request for a Technician account {company_line} at TechTalk has been approved!

You now have access to:
- Submit technical questions using voice, text, or images
- Get AI-powered troubleshooting assistance
- Access company-specific knowledge base

You can log in now at: https://juniortechbot.riff.works/techassist

Thank you for choosing TechTalk.

Best regards,
The TechTalk Team
"""
    
    # HTML version with basic formatting
    content_html = content_text.replace('\n\n', '</p><p>')
    content_html = f"<html><body><p>{content_html}</p></body></html>"
    
    try:
        # Send the email via Databutton notification
        db.notify.email(
            to=user_email,
            subject=subject,
            content_html=content_html,
            content_text=content_text,
        )
        
        # Log the email was sent
        db_firestore = get_firestore_client()
        if db_firestore:
            db_firestore.collection('auditLogs').add({
                'timestamp': firestore.SERVER_TIMESTAMP,
                'uid': 'system',
                'userEmail': 'system@techtalk.app',
                'userRole': 'system',
                'action': 'send_approval_email',
                'resourceType': 'user',
                'resourceId': user_email,
                'details': {
                    'emailType': 'approval',
                    'role': role,
                    'company': company
                }
            })
        
        return True
    except Exception as e:
        print(f"Error sending approval email: {e}")
        return False

def send_rejection_notification(user_email: str, user_name: str, role: str, reason: str, company: Optional[str] = None):
    subject = "Your TechTalk Account Request"
    
    # Create the message
    company_line = f"for {company}" if company else ""
    role_display = "Company Admin" if role == "company_admin" else "Technician"
    
    content_text = f"""Hello {user_name},

Thank you for your interest in TechTalk. 

Unfortunately, your request for a {role_display} account {company_line} has not been approved at this time.

Reason: {reason}

If you believe this is an error or would like more information, please contact support or your company administrator.

Best regards,
The TechTalk Team
"""
    
    # HTML version with basic formatting
    content_html = content_text.replace('\n\n', '</p><p>')
    content_html = f"<html><body><p>{content_html}</p></body></html>"
    
    try:
        # Send the email via Databutton notification
        db.notify.email(
            to=user_email,
            subject=subject,
            content_html=content_html,
            content_text=content_text,
        )
        
        # Log the email was sent
        db_firestore = get_firestore_client()
        if db_firestore:
            db_firestore.collection('auditLogs').add({
                'timestamp': firestore.SERVER_TIMESTAMP,
                'uid': 'system',
                'userEmail': 'system@techtalk.app',
                'userRole': 'system',
                'action': 'send_rejection_email',
                'resourceType': 'user',
                'resourceId': user_email,
                'details': {
                    'emailType': 'rejection',
                    'role': role,
                    'reason': reason,
                    'company': company
                }
            })
        
        return True
    except Exception as e:
        print(f"Error sending rejection email: {e}")
        return False

# Get pending user requests - system admin can see all, company admins only see their company's technicians
@router.get("/admin/pending-users")
async def get_pending_users(user: AuthorizedUser) -> PendingUserListResponse:
    """Get pending user requests for approval"""
    # Get Firestore database client
    db_firestore = get_firestore_client()
    if db_firestore is None:
        raise HTTPException(status_code=500, detail="Could not get Firestore client")
    
    try:
        # Get user's role and company from Firebase Auth
        # firebase_user = auth.get_user(user.sub)
        user_record = None
        
        # Get additional user info from Firestore
        user_doc = db_firestore.collection('users').document(user.sub).get()
        if user_doc.exists:
            user_record = user_doc.to_dict()
        else:
            raise HTTPException(status_code=403, detail="User not found in database")
        
        # Check user role authorization
        role = user_record.get('role')
        if not role or (role != 'system_admin' and role != 'company_admin'):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
            
        # Get company for company admins
        company = user_record.get('company') if role == 'company_admin' else None
        
        # Query the pending requests collection
        query_ref = db_firestore.collection('pendingRequests')
        
        # Company admins can only see technician requests for their company
        if role == 'company_admin':
            if not company:
                raise HTTPException(status_code=403, detail="Company admin without company assignment")
                
            # Only show technician requests for this company
            query_ref = query_ref.where('company', '==', company)
            query_ref = query_ref.where('requestedRole', '==', 'technician')
        elif role == 'system_admin':
            # System admins see all requests
            pass  # No additional filters needed for system admins
        
        # Query the pendingRequests collection
        # pending_users_query = db_firestore.collection('pendingRequests').stream()
        pending_users_query = query_ref.stream()
        
        # Convert to list of PendingUser objects
        pending_users = []
        for doc in pending_users_query:
            user_data = doc.to_dict()
            # Ensure UID is set
            uid = user_data.get('uid', doc.id)
            
            # Handle timestamp formatting with explicit type checks
            requested_at = None
            if 'requestedAt' in user_data:
                if hasattr(user_data['requestedAt'], 'seconds'):
                    # Handle Firestore timestamp
                    requested_at = {
                        'seconds': user_data['requestedAt'].seconds,
                        'nanoseconds': user_data['requestedAt'].nanoseconds
                    }
                elif isinstance(user_data['requestedAt'], dict) and 'seconds' in user_data['requestedAt']:
                    # Already in the right format
                    requested_at = user_data['requestedAt']
                elif isinstance(user_data['requestedAt'], (int, float)):
                    # Unix timestamp
                    requested_at = {'seconds': int(user_data['requestedAt']), 'nanoseconds': 0}
            
            # Format review timestamp if present
            reviewed_at = None
            if 'reviewedAt' in user_data:
                if hasattr(user_data['reviewedAt'], 'seconds'):
                    # Handle Firestore timestamp
                    reviewed_at = {
                        'seconds': user_data['reviewedAt'].seconds,
                        'nanoseconds': user_data['reviewedAt'].nanoseconds
                    }
                elif isinstance(user_data['reviewedAt'], dict) and 'seconds' in user_data['reviewedAt']:
                    # Already in the right format
                    reviewed_at = user_data['reviewedAt']
                elif isinstance(user_data['reviewedAt'], (int, float)):
                    # Unix timestamp
                    reviewed_at = {'seconds': int(user_data['reviewedAt']), 'nanoseconds': 0}
            
            # Create PendingUser object with robust fallbacks for all fields
            try:
                pending_user = PendingUser(
                    id=doc.id,
                    uid=uid,
                    userEmail=user_data.get('userEmail', user_data.get('email', '')),
                    displayName=user_data.get('displayName', ''),
                    requestedRole=user_data.get('requestedRole', user_data.get('role', 'technician')),
                    company=user_data.get('company'),
                    requestedAt=requested_at,
                    status=user_data.get('status', 'pending'),
                    reviewedBy=user_data.get('reviewedBy'),
                    reviewedAt=reviewed_at,
                    rejectionReason=user_data.get('rejectionReason')
                )
                pending_users.append(pending_user)
            except Exception as e:
                print(f"Error processing pending user {doc.id}: {e}")
                # Continue processing other users instead of failing completely
                continue
        
        # Return properly formatted response with both users and total fields
        return PendingUserListResponse(users=pending_users, total=len(pending_users))
        
    except Exception as e:
        print(f"Error fetching pending users: {e}")
        # Return empty list instead of raising an exception
        return PendingUserListResponse(users=[], total=0)

# Approve or reject a user request
@router.post("/admin/approve-user")
async def approve_reject_user(user: AuthorizedUser, background_tasks: BackgroundTasks, request: ApproveRejectRequest) -> ApproveRejectResponse:
    """Approve or reject a user request"""
    # Get Firestore database client
    db_firestore = get_firestore_client()
    if db_firestore is None:
        raise HTTPException(status_code=500, detail="Could not get Firestore client")
    try:
        print(f"Processing approval/rejection for user {request.userId}")
        print(f"Debug - Full request object: {request}")
        
        # Get user's role and company from Firebase Auth
        firebase_user = auth.get_user(user.sub)
        user_record = None
        
        # Get additional user info from Firestore
        user_doc = db_firestore.collection('users').document(user.sub).get()
        if user_doc.exists:
            user_record = user_doc.to_dict()
        else:
            raise HTTPException(status_code=403, detail="User not found in database")
        
        # Check user role authorization
        role = user_record.get('role')
        if not role or (role != 'system_admin' and role != 'company_admin'):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
            
        # Get company for company admins
        approver_company = user_record.get('company') if role == 'company_admin' else None
        
        # Get the pending request from Firestore
        pending_request_doc = db_firestore.collection('pendingRequests').document(request.userId).get()
        if not pending_request_doc.exists:
            raise HTTPException(status_code=404, detail="Request not found")
            
        pending_request = pending_request_doc.to_dict()
        print(f"Found pending request for {request.userId}: {pending_request}")
        
        # Validate approver has permission to approve/reject this request
        requestor_role = pending_request.get('requestedRole')
        requestor_company = pending_request.get('company')
        
        # Company admins can only approve technicians in their company
        if role == 'company_admin':
            if requestor_role != 'technician':
                raise HTTPException(status_code=403, detail="Company admins can only approve technician requests")
                
            if approver_company != requestor_company:
                raise HTTPException(status_code=403, detail="You can only approve technicians in your company")
        
        # Update the user's status in Firestore
        user_to_update_id = pending_request_doc.id  # Use document ID as the user ID
        user_to_update_doc = db_firestore.collection('users').document(user_to_update_id)
        
        # Update the pending request status
        pending_request_ref = db_firestore.collection('pendingRequests').document(request.userId)
        
        timestamp = firestore.SERVER_TIMESTAMP
        
        if request.approve:
            print(f"Approving user {user_to_update_id} with role {requestor_role}")
            # Approve the user
            try:
                # 1. Check if user document exists and create or update accordingly
                user_doc = user_to_update_doc.get()
                if user_doc.exists:
                    user_to_update_doc.update({
                    'approvalStatus': 'approved',
                    'role': request.role if request.role else requestor_role,
                })
                else:
                    # Create new document with all required fields
                    user_to_update_doc.set({
                        'uid': user_to_update_id,
                        'email': pending_request.get('userEmail', pending_request.get('email', '')),
                        'displayName': pending_request.get('displayName', ''),
                        'approvalStatus': 'approved',
                        'role': request.role if request.role else requestor_role,
                        'company': requestor_company,
                        'status': 'active',
                        'createdAt': firestore.SERVER_TIMESTAMP,
                        'approvedAt': firestore.SERVER_TIMESTAMP,
                        'approvedBy': user.sub,
                        'lastActive': firestore.SERVER_TIMESTAMP
                }, merge=True)
            
                # 2. Update Firebase custom claims to add role
                assigned_role = request.role if request.role else requestor_role
                user_claims = {
                    'role': assigned_role,
                    'company': requestor_company
                }
                auth.set_custom_user_claims(user_to_update_id, user_claims)
                print(f"Set custom claims for {user_to_update_id}: {user_claims}")
    
                # 3. Create or update user document in users collection
                db_firestore.collection('users').document(user_to_update_id).set({
                    'uid': user_to_update_id,
                    'email': pending_request.get('userEmail', pending_request.get('email', '')),
                    'displayName': pending_request.get('displayName', ''),
                    'role': assigned_role,
                    'company': requestor_company,
                    'status': 'active',
                    'approvalStatus': 'approved',
                    'approvedAt': timestamp,
                    'approvedBy': user.sub
                }, merge=True)
                
                # 4. Update pending request
                pending_request_ref.update({
                    'status': 'approved',
                    'reviewedBy': user.sub,
                    'reviewedAt': timestamp,
                })
                
                # 5. Schedule email notification
                user_email = pending_request.get('userEmail', pending_request.get('email', ''))
                user_name = pending_request.get('displayName', '')
                
                # Run as background task so the API response is fast
                background_tasks.add_task(
                    send_approval_notification,
                    user_email=user_email,
                    user_name=user_name,
                    role=requestor_role,
                    company=requestor_company
                )
                
                # 6. Record action in audit log
                db_firestore.collection('auditLogs').add({
                    'timestamp': timestamp,
                    'uid': user.sub,
                    'userEmail': firebase_user.email,
                    'userRole': role,
                    'company': approver_company,
                    'action': 'approve_user',
                    'resourceType': 'user',
                    'resourceId': user_to_update_id,
                    'details': {
                        'approvedRole': requestor_role,
                        'approvedCompany': requestor_company
                    }
                })
                            
                # 7. Delete from pendingRequests collection
                db_firestore.collection('pendingRequests').document(user_to_update_id).delete()
                print(f"Deleted pending request for {user_to_update_id}")
                message = f"User {user_to_update_id} approved successfully"
            except Exception as e:
                print(f"Error during user approval: {e}")
                raise HTTPException(status_code=500, detail=f"Error during user approval: {str(e)}")
                
        else:
            print(f"Rejecting user {user_to_update_id}")
            # Reject the user
            try:
                if not request.rejectionReason:
                    raise HTTPException(status_code=400, detail="Rejection reason is required")
                    
                # 1. Update user record
                # 1. Check if user document exists and create or update accordingly
                user_doc = user_to_update_doc.get()
                if user_doc.exists:
                    user_to_update_doc.update({
                    'approvalStatus': 'rejected',
                    'rejectionReason': request.rejectionReason
                })
                else:
                    # Create new document with all required fields
                    user_to_update_doc.set({
                    'uid': user_to_update_id,
                    'email': pending_request.get('userEmail', pending_request.get('email', '')),
                    'displayName': pending_request.get('displayName', ''),
                    'approvalStatus': 'rejected',
                    'rejectionReason': request.rejectionReason,
                    'company': requestor_company,
                    'status': 'inactive',
                    'createdAt': firestore.SERVER_TIMESTAMP, 
                    'rejectedAt': firestore.SERVER_TIMESTAMP,
                    'rejectedBy': user.sub,
                    'role': requestor_role  # Store the requested role even though rejected
            }, merge=True)
                
                # 2. Update pending request
                pending_request_ref.update({
                    'status': 'rejected',
                    'reviewedBy': user.sub,
                    'reviewedAt': timestamp,
                    'rejectionReason': request.rejectionReason
                })
                
                # 3. Schedule email notification
                user_email = pending_request.get('userEmail', pending_request.get('email', ''))
                user_name = pending_request.get('displayName', '')
                
                # Run as background task so the API response is fast
                background_tasks.add_task(
                    send_rejection_notification,
                    user_email=user_email,
                    user_name=user_name,
                    role=requestor_role,
                    reason=request.rejectionReason,
                    company=requestor_company
                )
                
                # 4. Record action in audit log
                db_firestore.collection('auditLogs').add({
                    'timestamp': timestamp,
                    'uid': user.sub,
                    'userEmail': firebase_user.email,
                    'userRole': role,
                    'company': approver_company,
                    'action': 'reject_user',
                    'resourceType': 'user',
                    'resourceId': user_to_update_id,
                    'details': {
                        'rejectedRole': requestor_role,
                        'rejectionReason': request.rejectionReason
                    }
                })
                # 5. Delete from pendingRequests
                db_firestore.collection('pendingRequests').document(user_to_update_id).delete()
                print(f"Deleted pending request for {user_to_update_id}")
                
                message = f"User {user_to_update_id} request rejected"
            except Exception as e:
                print(f"Error during user rejection: {e}")
                raise HTTPException(status_code=500, detail=f"Error during user rejection: {str(e)}")
        
        # Return success response with the correct userId
        return ApproveRejectResponse(
            success=True,
            message=message,
            userId=user_to_update_id
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions directly
        raise e
    except Exception as e:
        print(f"Error approving/rejecting user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process request: {str(e)}")

# Get available domains
@router.get("/admin/domains")
async def get_available_domains(user: AuthorizedUser) -> DomainListResponse:
    """Get list of available domains for assignment"""
    from app.libs.constraint_manager import DOMAINS
    return DomainListResponse(domains=DOMAINS)

# Assign domain to user
@router.post("/admin/assign-domain")
async def assign_user_domain(request: AssignDomainRequest, user: AuthorizedUser) -> AssignDomainResponse:
    """Assign a specific domain to a user (Company Admin only)"""
    # Get Firestore database client
    db_firestore = get_firestore_client()
    if db_firestore is None:
        raise HTTPException(status_code=500, detail="Could not get Firestore client")
    
    try:
        from app.libs.constraint_manager import DOMAINS
        
        # Validate domain
        if request.domain not in DOMAINS:
            raise HTTPException(status_code=400, detail=f"Invalid domain. Must be one of: {', '.join(DOMAINS.keys())}")
            
        # Get requester info to verify permissions
        requester_doc = db_firestore.collection('users').document(user.sub).get()
        if not requester_doc.exists:
            raise HTTPException(status_code=403, detail="Requester not found")
            
        requester_data = requester_doc.to_dict()
        requester_role = requester_data.get('role')
        requester_company = requester_data.get('company')
        
        if requester_role not in ['company_admin', 'system_admin']:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
            
        # Get target user
        target_ref = db_firestore.collection('users').document(request.userId)
        target_doc = target_ref.get()
        
        if not target_doc.exists:
            raise HTTPException(status_code=404, detail="Target user not found")
            
        target_data = target_doc.to_dict()
        
        # Verify company access for company admins
        if requester_role == 'company_admin':
            if target_data.get('company') != requester_company:
                raise HTTPException(status_code=403, detail="Cannot assign domain to user from another company")
                
        # Update user
        target_ref.update({
            'assignedDomain': request.domain,
            'updatedAt': firestore.SERVER_TIMESTAMP,
            'updatedBy': user.sub
        })
        
        # Log action
        db_firestore.collection('auditLogs').add({
            'timestamp': firestore.SERVER_TIMESTAMP,
            'uid': user.sub,
            'action': 'assign_domain',
            'resourceType': 'user',
            'resourceId': request.userId,
            'details': {
                'domain': request.domain,
                'previousDomain': target_data.get('assignedDomain')
            }
        })
        
        return AssignDomainResponse(
            success=True,
            message=f"Domain '{DOMAINS[request.domain]}' assigned to user successfully",
            userId=request.userId,
            assignedDomain=request.domain
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error assigning domain: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to assign domain: {str(e)}")

# Get all users (for system admin) or company users (for company admin)
@router.get("/admin/users")
async def get_all_users(user: AuthorizedUser, approval_status_list_str: Optional[str] = Query(None, description="Comma-separated list of approval statuses to filter by (e.g., 'approved' or 'rejected')")) -> UserListResponse:
    """Get all users in the system"""
    # Get Firestore database client
    db_firestore = get_firestore_client()
    if db_firestore is None:
        raise HTTPException(status_code=500, detail="Could not get Firestore client")
    
    try:
        # Get user's role and company from Firebase Auth
        # firebase_user = auth.get_user(user.sub)
        user_record = None
        
        # Get additional user info from Firestore
        user_doc = db_firestore.collection('users').document(user.sub).get()
        if user_doc.exists:
            user_record = user_doc.to_dict()
        else:
            raise HTTPException(status_code=403, detail="User not found in database")
        
        # Check user role authorization
        role = user_record.get('role')
        if not role or (role != 'system_admin' and role != 'company_admin'):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
            
        # Get company for company admins
        company = user_record.get('company') if role == 'company_admin' else None
        
        # Query the users collection
        query_ref = db_firestore.collection('users')
        
        # Company admins can only see users in their company
        if role == 'company_admin':
            if not company:
                raise HTTPException(status_code=403, detail="Company admin without company assignment")
            query_ref = query_ref.where('company', '==', company)
        
        # Filter by approvalStatus if provided
        if approval_status_list_str:
            approval_statuses_to_query = [status.strip() for status in approval_status_list_str.split(',') if status.strip()]
            if approval_statuses_to_query:
                if len(approval_statuses_to_query) > 10: # Firestore 'in' query limit
                    raise HTTPException(status_code=400, detail="Too many approval statuses requested. Maximum 10.")
                query_ref = query_ref.where('approvalStatus', 'in', approval_statuses_to_query)
        
        # Get all users
        results = query_ref.get()
        
        # Convert to response model
        users_data = []
        for doc in results:
            try:
                data = doc.to_dict()
                
                # Skip if missing required fields
                if 'email' not in data:
                    continue
                    
                # Handle different timestamp formats
                created_at = None
                if 'createdAt' in data:
                    if hasattr(data['createdAt'], 'seconds'):
                        # Firestore timestamp
                        created_at = {
                            'seconds': data['createdAt'].seconds,
                            'nanoseconds': data['createdAt'].nanoseconds
                        }
                    elif isinstance(data['createdAt'], dict) and 'seconds' in data['createdAt']:
                        # Already in the right format
                        created_at = data['createdAt']
                    elif isinstance(data['createdAt'], str):
                        # ISO format string - convert to timestamp
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(data['createdAt'])
                            created_at = {
                                'seconds': int(dt.timestamp()),
                                'nanoseconds': 0
                            }
                        except:
                            # Fallback if parsing fails
                            created_at = {'seconds': 0, 'nanoseconds': 0}
                
                if not created_at:
                    created_at = {'seconds': 0, 'nanoseconds': 0}
                
                # Handle last active timestamp
                last_active = None
                if 'lastActive' in data:
                    if hasattr(data['lastActive'], 'seconds'):
                        # Firestore timestamp
                        last_active = {
                            'seconds': data['lastActive'].seconds,
                            'nanoseconds': data['lastActive'].nanoseconds
                        }
                    elif isinstance(data['lastActive'], dict) and 'seconds' in data['lastActive']:
                        # Already in the right format
                        last_active = data['lastActive']
                    elif isinstance(data['lastActive'], str):
                        # ISO format string - convert to timestamp
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(data['lastActive'])
                            last_active = {
                                'seconds': int(dt.timestamp()),
                                'nanoseconds': 0
                            }
                        except:
                            # Fallback if parsing fails
                            pass
                
                # Create user data object with fallbacks
                users_data.append(UserData(
                    id=doc.id,
                    uid=data.get('uid', doc.id),
                    email=data.get('email', ''), # Ensure email is present as it's not Optional in UserData
                    displayName=data.get('displayName'),
                    role=data.get('role'),
                    company=data.get('company'),
                    status=data.get('status'),
                    approvalStatus=data.get('approvalStatus'),
                    assignedDomain=data.get('assignedDomain'),
                    createdAt=parse_firestore_timestamp(data.get('createdAt')),
                    lastActive=parse_firestore_timestamp(data.get('lastActive')),
                    approvedAt=parse_firestore_timestamp(data.get('approvedAt')),
                    rejectedAt=parse_firestore_timestamp(data.get('rejectedAt')),
                    approvedBy=data.get('approvedBy'),
                    rejectedBy=data.get('rejectedBy'),
                    rejectionReason=data.get('rejectionReason'),
                    photoURL=data.get('photoURL')
                ))
            except Exception as e:
                print(f"Error processing user {doc.id}: {e}")
                # Continue processing other users instead of failing completely
                continue
            
        # Return response
        return UserListResponse(users=users_data, total=len(users_data))
    except Exception as e:
        print(f"Error fetching users: {e}")
        # Return empty list instead of raising an exception
        return UserListResponse(users=[], total=0)
