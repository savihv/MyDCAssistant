

import firebase_admin
from firebase_admin import credentials, storage as fb_admin_storage
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.auth import AuthorizedUser
import databutton as db
import json
import uuid
from pydantic import BaseModel
import re

from app.libs.firebase_config import get_storage_bucket, FIREBASE_BUCKET_NAME

router = APIRouter(prefix="/uploads", tags=["Uploads"])


class GeneralFileUploadResponse(BaseModel):
    gcs_path: str
    filename: str


@router.post("/upload_general_file", response_model=GeneralFileUploadResponse)
async def upload_general_file(
    user: AuthorizedUser,
    file: UploadFile = File(...),
):
    """
    Handles general-purpose file uploads using the Firebase Admin SDK.
    This ensures consistent authentication with the rest of the application.
    """
    if not get_storage_bucket():
        raise HTTPException(status_code=503, detail="Storage service is not available.")

    # _storage_bucket_client is the actual bucket object from the initialized Firebase app
    bucket = get_storage_bucket()

    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename cannot be empty.")

        # Extract and sanitize file extension
        if '.' in file.filename:
            file_extension = file.filename.split('.')[-1]
            # Sanitize extension: only allow alphanumeric and limit length
            file_extension = re.sub(r'[^a-zA-Z0-9]', '', file_extension)[:10]
            if not file_extension:
                file_extension = 'bin'
        else:
            file_extension = 'bin'

        safe_filename = str(uuid.uuid4())
        blob_name = f"general-uploads/{user.sub}/{safe_filename}.{file_extension}"
        
        blob = bucket.blob(blob_name)
        
        content = await file.read()
        blob.upload_from_string(content, content_type=file.content_type)
        
        gcs_path = f"gs://{FIREBASE_BUCKET_NAME}/{blob_name}"
        
        print(f"User {user.email} uploaded file '{file.filename}' to '{gcs_path}'.")

        return GeneralFileUploadResponse(gcs_path=gcs_path, filename=file.filename)

    except Exception as e:
        print(f"ERROR during general file upload for user {user.email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")
