from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import firebase_admin
from firebase_admin import auth, credentials, firestore
import databutton as db
import json
from typing import Optional
from datetime import datetime
import traceback

# Use centralized lazy Firebase initialization
from app.libs.firebase_config import get_firestore_client

router = APIRouter()

# Initialize Firebase Admin SDK if not already initialized
# Firebase Admin SDK is now initialized centrally in src/main.py

class DirectRegistrationRequest(BaseModel):
    email: str
    password: str
    displayName: str
    role: str = "technician"
    company: Optional[str] = None
    location: Optional[str] = None
    force_recreate: bool = False  # Option to delete and recreate a user if email already exists

class DirectRegistrationResponse(BaseModel):
    success: bool
    userId: Optional[str] = None
    message: str

@router.post("/direct-approve-user2")
async def direct_approve_user2(request: DirectRegistrationRequest) -> DirectRegistrationResponse:
    """
    Creates a user account with proper hierarchical approval workflow:
    - System Admins are auto-approved
    - Company Admins require System Admin approval
    - Technicians require Company Admin approval
    """
    try:
        # Get Firestore client (lazy initialization)
        db_firestore = get_firestore_client()
        
        # Input validation
        if not request.email or "@" not in request.email:
            return DirectRegistrationResponse(
                success=False,
                userId=None,
                message="Invalid email format"
            )

        if not request.password or len(request.password) < 6:
            return DirectRegistrationResponse(
                success=False,
                userId=None,
                message="Password must be at least 6 characters"
            )
            
        if not request.displayName or len(request.displayName.strip()) < 2:
            return DirectRegistrationResponse(
                success=False,
                userId=None,
                message="Display name is required and must be at least 2 characters"
            )
            
        # Validate role
        valid_roles = ["technician", "company_admin", "system_admin"]
        if request.role not in valid_roles:
            return DirectRegistrationResponse(
                success=False,
                userId=None,
                message=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
        
        # Check if email already exists and handle appropriately
        try:
            # Try to get user by email first
            existing_user = None
            try:
                existing_user = auth.get_user_by_email(request.email)
                print(f"Found existing user with email {request.email}: {existing_user.uid}")
                
                # Check if we should delete and recreate the user
                # This helps with the "email already exists" issue when testing
                if request.force_recreate:
                    try:
                        # Get Firestore client
                        db_firestore = get_firestore_client()
                        
                        # Delete from Firestore first
                        try:
                            db_firestore.collection("users").document(existing_user.uid).delete()
                            print(f"Deleted user {existing_user.uid} from Firestore")
                        except Exception as e:
                            print(f"Warning: Could not delete user from Firestore: {e}")
                        
                        # Then delete from Auth
                        auth.delete_user(existing_user.uid)
                        print(f"Deleted user {existing_user.uid} from Firebase Auth")
                        
                        # Wait a moment for deletion to propagate
                        existing_user = None
                    except Exception as e:
                        print(f"Error deleting existing user: {e}")
                        return DirectRegistrationResponse(
                            success=False,
                            userId=None,
                            message=f"Error recreating user: {str(e)}"
                        )
                else:
                    return DirectRegistrationResponse(
                        success=False,
                        userId=None,
                        message="Email already exists. Please use a different email address."
                    )
            except auth.UserNotFoundError:
                # User doesn't exist, which is what we want for creation
                pass
            
            # Create the user if it doesn't exist
            user = None
            if not existing_user:
                # 1. Create the user in Firebase Auth
                try:
                    user = auth.create_user(
                        email=request.email,
                        password=request.password,
                        display_name=request.displayName,
                        disabled=False
                    )
                    print(f"Created Firebase Auth user: {user.uid}")
                except auth.EmailAlreadyExistsError:
                    return DirectRegistrationResponse(
                        success=False,
                        userId=None,
                        message="Email already exists. Please use a different email address."
                    )
                except auth.InvalidEmailError:
                    return DirectRegistrationResponse(
                        success=False,
                        userId=None,
                        message="Invalid email format."
                    )
                except auth.WeakPasswordError:
                    return DirectRegistrationResponse(
                        success=False,
                        userId=None,
                        message="Password is too weak. It must be at least 6 characters long."
                    )
                except Exception as e:
                    print(f"Error creating Firebase Auth user: {e}")
                    return DirectRegistrationResponse(
                        success=False,
                        userId=None,
                        message=f"Error creating user: {str(e)}"
                    )
            else:
                user = existing_user
                
            # 2. Set custom claims for role-based access control
            claims_set = False
            try:
                # Set approval status based on role hierarchy
                approval_status = "pending"
                if request.role == "system_admin":
                    approval_status = "approved"  # Auto-approve system admins
                
                claims = {
                    "role": request.role,
                    "approvalStatus": approval_status,
                }
                
                # Add company to claims if provided
                if request.company:
                    claims["company"] = request.company
                    
                # Add location to claims if provided
                if request.location:
                    claims["location"] = request.location
                
                # Set claims and verify they were set properly
                print(f"Setting custom claims for user {user.uid}: {claims}")
                auth.set_custom_user_claims(user.uid, claims)
                
                # Verify claims were set by checking the user again
                updated_user = auth.get_user(user.uid)
                user_claims = updated_user.custom_claims or {}
                print(f"Verified claims for user {user.uid}: {user_claims}")
                
                # Check that all expected claims are present
                claims_set = all(user_claims.get(key) == value for key, value in claims.items())
                if not claims_set:
                    print(f"Warning: Claims verification failed. Expected: {claims}, Got: {user_claims}")
                
            except Exception as e:
                print(f"Error setting claims for user {user.uid}: {e}")
                # Continue execution - we'll note this in the response
            
            # 3. Create user profile in Firestore
            firestore_success = False
            try:
                db_firestore = get_firestore_client()
                # Set same approval status in Firestore as in claims
                approval_status = "pending"
                if request.role == "system_admin":
                    approval_status = "approved"  # Auto-approve system admins
                    
                user_data = {
                    "uid": user.uid,
                    "email": request.email,
                    "displayName": request.displayName,
                    "role": request.role,
                    "approvalStatus": approval_status,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "lastActive": firestore.SERVER_TIMESTAMP,
                }
                
                # Add optional fields if provided
                if request.company:
                    user_data["company"] = request.company
                    
                if request.location:
                    user_data["location"] = request.location
                    
                # Save to Firestore
                db_firestore.collection("users").document(user.uid).set(user_data)
                print(f"Created user profile in Firestore for {user.uid}")
                firestore_success = True
                
            except Exception as e:
                print(f"Warning: Error creating Firestore profile: {e}")
                # Continue execution, not critical
                
            # 4. Return successful response with status details
            approval_message = "automatically approved" if request.role == "system_admin" else "pending approval"
            message = f"User created and {approval_message}."
            if not claims_set:
                message += " Warning: Role permissions may not have been applied correctly."
            if not firestore_success:
                message += " Warning: User profile may not have been created in database."
                
            return DirectRegistrationResponse(
                success=True,
                userId=user.uid,
                message=message
            )
                
        except Exception as e:
            print(f"Error in user creation/verification process: {e}")
            print(traceback.format_exc())
            return DirectRegistrationResponse(
                success=False,
                userId=None,
                message=f"Error creating user: {str(e)}"
            )
        
    except Exception as e:
        print(f"Uncaught exception in direct_approve_user2: {e}")
        print(traceback.format_exc())
        return DirectRegistrationResponse(
            success=False,
            userId=None,
            message=f"Error creating user: {str(e)}"
        )
