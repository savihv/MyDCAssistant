

import asyncio  # Add this import at the top if not already present
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from typing import List, Optional
import databutton as db
import json
from google.cloud import firestore, storage  # type: ignore
from google.oauth2 import service_account  # type: ignore
import uuid
from app.auth import AuthorizedUser
import datetime
from pydantic import BaseModel
from firebase_admin import auth  # type: ignore # <-- ADD THIS IMPORT
from app.libs.firebase_config import get_firestore_client, get_storage_bucket

router = APIRouter(prefix="/expert-tips", tags=["Expert Tips"])

class CreateExpertTipEntryRequest(BaseModel):
    title: str
    description: str
    mediaUrls: List[str] = []
    target_index: str = "expert" 

@router.post("/create-entry", summary="Creates an expert tip entry in Firestore after files are uploaded")
async def create_expert_tip_entry(
    user: AuthorizedUser,
    request: CreateExpertTipEntryRequest
):
    """
    Handles the creation of the expert tip database entry.
    This endpoint assumes media files have already been uploaded to GCS
    and their URLs are provided in the request.
    """
    firestore_client = get_firestore_client()
    
    # Correctly get user details from Firebase Auth custom claims
    try:
        user_record = await asyncio.to_thread(auth.get_user, user.sub)
        # Get company from custom claims, fall back to "Unknown Company" if not present
        company_id = user_record.custom_claims.get('company', 'Unknown Company')
        # Get display name from the user record, fall back to what's in the token or a default
        display_name = user_record.display_name or user.name or 'Unknown User'

        if not company_id or company_id == 'Unknown Company':
             print(f"Warning: Could not find 'company' in custom claims for user {user.sub}.")

    except Exception as e:
        print(f"Error fetching user record from Firebase Auth for {user.sub}: {e}")
        # Provide sensible defaults if auth lookup fails
        company_id = "Unknown Company"
        display_name = user.name or "Unknown User"
        
    target_index_name = request.target_index or "expert"
    #sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index_name).lower()

    # Prepare data for Firestore document
    tip_data = {
        "technicianId": user.sub,
        "technicianName": display_name,
        "company": company_id,
        "title": request.title,
        "description": request.description,
        "mediaUrls": request.mediaUrls,
        "audioUrl": None, # This can be deprecated or handled differently if needed
        "createdAt": firestore.SERVER_TIMESTAMP,
        "status": "pending_review",
        "isAddedToKnowledgeBase": False,
        "target_index": target_index_name,
    }

    # Create new document in 'expert_tips' collection
    try:
        await asyncio.to_thread(firestore_client.collection("expert_tips").add, tip_data)
        return {"message": "Expert tip submitted successfully for review."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save expert tip: {str(e)}")
