from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import firebase_admin
from firebase_admin import auth, firestore
import databutton as db
import json
from typing import Optional
from datetime import datetime

# Use centralized lazy Firebase initialization
from app.libs.firebase_config import get_firestore_client

router = APIRouter()

class UserRegistrationRequest(BaseModel):
    email: str
    password: str
    displayName: str
    role: str
    company: Optional[str] = None
    location: Optional[str] = None
    organization: Optional[str] = None # <-- ADD THIS LINE

class UserRegistrationResponse(BaseModel):
    success: bool
    userId: Optional[str] = None
    message: str
    approvalStatus: str = "pending_approval"

@router.post("/register")
def register_user(request: UserRegistrationRequest) -> UserRegistrationResponse:
    """
    Register a new user using Firebase Admin SDK.
    This handles both the Firebase Auth account creation and Firestore document creation.
    """
    try:
        # Get Firestore client (lazy initialization)
        db_firestore = get_firestore_client()
        
        # 1. Create the user in Firebase Auth
        user = auth.create_user(
            email=request.email,
            password=request.password,
            display_name=request.displayName,
            disabled=False
        )
        
        # Set custom claims for role-based access control
        claims = {
            "role": request.role,
            "approvalStatus": "pending_approval"
        }
        auth.set_custom_user_claims(user.uid, claims)
        
        # 2. Create the user document in Firestore
        now = datetime.now()
        user_data = {
            "uid": user.uid,
            "email": request.email,
            "displayName": request.displayName,
            "role": request.role,
            "approvalStatus": "pending_approval",  # Default to pending approval
            "createdAt": now,
            "lastActive": now,
        }
        
        # Add optional fields
        if request.company:
            user_data["company"] = request.company
        
        if request.location:
            user_data["location"] = request.location

        
        if request.organization: # <-- ADD THIS BLOCK
            user_data["organization"] = request.organization
            
        # 3. Save to Firestore - users collection
        db_firestore.collection("users").document(user.uid).set(user_data)
        
        # 4. Create a pending request for approval
        pending_request_data = {
            "id": user.uid,  # Use user ID as request ID
            "userId": user.uid,
            "userEmail": request.email,
            "displayName": request.displayName,
            "requestedRole": request.role,
            "company": request.company or None,
            "organization": request.organization or None, # <-- ADD THIS LINE
            "requestedAt": now,
            "status": "pending"
        }
        
        # Save to pendingRequests collection
        db_firestore.collection("pendingRequests").document(user.uid).set(pending_request_data)
        
        return UserRegistrationResponse(
            success=True,
            userId=user.uid,
            message="User registered successfully. Your account is pending approval.",
            approvalStatus="pending_approval"
        )
        
    except Exception as e:
        # Log the error for debugging
        print(f"Error registering user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error registering user: {str(e)}")
