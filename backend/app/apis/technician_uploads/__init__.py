import firebase_admin
from firebase_admin import credentials, storage as fb_admin_storage, firestore as fb_admin_firestore
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from app.auth import AuthorizedUser
import databutton as db
import json
import uuid
import os
from pydantic import BaseModel # Added for response model
import re

from app.libs.firebase_config import get_firestore_client, get_storage_bucket, FIREBASE_BUCKET_NAME

router = APIRouter(prefix="/technician_uploads") # Added prefix for clarity

class FileUploadResponse(BaseModel): # Using Pydantic BaseModel from pydantic
    message: str
    gcs_path: str
    filename: str
    session_id: str

@router.post("/upload_file", response_model=FileUploadResponse)
async def upload_technician_file_v2(
    user: AuthorizedUser, # Corrected dependency
    sessionId: str = Form(...),
    file: UploadFile = File(...)
):
    if not get_firestore_client() or not get_storage_bucket():
        print(f"ERROR [technician_uploads - /upload_file]: Firebase services not available. Cannot upload for session {sessionId}.")
        raise HTTPException(status_code=503, detail="Firebase service not available. Please try again later.")

    print(f"INFO [technician_uploads - /upload_file]: User '{user.email}' (UID: '{user.sub}') attempting to upload file for session: {sessionId}")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty.")

    # Validate sessionId format (should be alphanumeric Firestore doc ID)
    if not re.match(r'^[a-zA-Z0-9_-]+$', sessionId):
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    # Sanitize filename and prepend a UUID to ensure uniqueness
    original_filename = file.filename.rsplit('/', 1)[-1] # Get only the filename, not path
    safe_filename = "".join(c if c.isalnum() or c in ('.', '_', '-') else '_' for c in original_filename)
    unique_filename = f"{uuid.uuid4().hex[:8]}_{safe_filename}"

    destination_blob_name = f"media/{sessionId}/{unique_filename}"
    gcs_path = f"gs://{FIREBASE_BUCKET_NAME}/{destination_blob_name}"

    try:
        print(f"INFO [technician_uploads - /upload_file]: Attempting to upload to GCS path: {gcs_path}")
        blob = get_storage_bucket().blob(destination_blob_name)
        
        contents = await file.read() # Read file content
        blob.upload_from_string(contents, content_type=file.content_type)
        await file.close() # Close the file
        
        print(f"INFO [technician_uploads - /upload_file]: Successfully uploaded {unique_filename} to {gcs_path}")

        # Update Firestore
        session_doc_ref = get_firestore_client().collection('troubleshootingSessions').document(sessionId)
        
        # Prepare data for Firestore update
        update_data = {
            'mediaGcsPaths': fb_admin_firestore.ArrayUnion([gcs_path]),
            'lastUpdatedBy': user.email, # Store who last updated
            'lastUpdated': fb_admin_firestore.SERVER_TIMESTAMP
        }
        
        session_doc_ref.set(update_data, merge=True) # Use set with merge=True to create or update
        print(f"INFO [technician_uploads - /upload_file]: Successfully updated Firestore for session {sessionId} with GCS path: {gcs_path}")

        return FileUploadResponse(
            message="File uploaded and session updated successfully.",
            gcs_path=gcs_path,
            filename=unique_filename,
            session_id=sessionId
        )
    except firebase_admin.exceptions.FirebaseError as e:
        print(f"ERROR [technician_uploads - /upload_file]: Firebase Admin SDK error during upload/Firestore update: {e}")
        raise HTTPException(status_code=500, detail=f"Firebase error processing file: {e}")
    except Exception as e:
        print(f"ERROR [technician_uploads - /upload_file]: Unexpected error during file processing: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected server error processing file: {e}")
