from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import AuthorizedUser
from app.apis.user_management import approve_reject_user, ApproveRejectRequest

router = APIRouter()

class DirectApproveRequest(BaseModel):
    """Request model for direct user approval"""
    uid: str
    approved: bool
    rejection_reason: str = None

class DirectApproveResponse(BaseModel):
    """Response model for direct user approval"""
    success: bool
    message: str
    details: dict

@router.post("/direct-approve")
async def direct_approve_user(user: AuthorizedUser, request: DirectApproveRequest, background_tasks: BackgroundTasks):
    """Directly approve or reject a user without needing the admin UI"""
    try:
        # Create request object for the user_management API
        approval_request = ApproveRejectRequest(
            userId=request.uid,
            approve=request.approved,
            rejectionReason=request.rejection_reason
        )
        
        # Call the existing approve_reject_user function
        result = await approve_reject_user(user, background_tasks, approval_request)
        
        return DirectApproveResponse(
            success=True,
            message=f"User {request.uid} {'approved' if request.approved else 'rejected'} successfully",
            details={"result": result.dict()}
        )
    except HTTPException as e:
        return DirectApproveResponse(
            success=False,
            message=f"Error: {e.detail}",
            details={"status_code": e.status_code}
        )
    except Exception as e:
        return DirectApproveResponse(
            success=False,
            message=f"Unexpected error: {str(e)}",
            details={}
        )