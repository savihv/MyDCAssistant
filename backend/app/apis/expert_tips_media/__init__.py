

# Suggested filepath: src/app/apis/expert_tips_media/__init__.py

import datetime
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Firebase and Google Cloud imports
from google.cloud import storage  # type: ignore
from google.oauth2 import service_account  # type: ignore
import firebase_admin  # type: ignore
from firebase_admin import credentials as fb_credentials, firestore as fb_firestore  # type: ignore

import databutton as db
from app.auth import AuthorizedUser
from app.libs.firebase_config import get_firestore_client, get_firebase_credentials_dict

# --- API Router Setup ---
router = APIRouter(prefix="/expert-tips-media", tags=["Expert Tips Media"])


# --- Pydantic Models ---
class SecureMediaUrlsResponse(BaseModel):
    """Response model containing a list of secure, signed URLs for media files."""
    secure_urls: list[str]

# --- Helper Function ---
def _generate_signed_url(storage_client: storage.Client, gcs_path: str) -> str | None:
    """Generates a v4 signed URL for a given GCS path."""
    if not gcs_path or not gcs_path.startswith("gs://"):
        print(f"Skipping invalid GCS path: {gcs_path}")
        return None

    try:
        path_parts = gcs_path.replace("gs://", "").split("/", 1)
        if len(path_parts) < 2:
            print(f"Cannot parse bucket/blob from path: {gcs_path}")
            return None
        bucket_name, blob_name = path_parts

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        expiration_time = datetime.timedelta(minutes=15)
        return blob.generate_signed_url(
            version="v4",
            expiration=expiration_time,
            method="GET",
        )
    except Exception as e:
        print(f"Error generating signed URL for {gcs_path}: {e}")
        return None

# --- API Endpoint ---
@router.get(
    "/{tip_id}",
    response_model=SecureMediaUrlsResponse,
    summary="Get Secure URLs for an Expert Tip's Media",
)

async def get_secure_media_urls_for_tip(tip_id: str, user: AuthorizedUser):
    """
    Generates secure, temporary URLs for all media files associated with a specific expert tip.
    """
    try:
        # 1. Get Firestore client from centralized config
        db_firestore = get_firestore_client()
        if db_firestore is None:
            raise HTTPException(status_code=500, detail="Could not get Firestore client")

        # 2. Get Storage client using centralized Firebase credentials
        creds_dict = get_firebase_credentials_dict()
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        storage_client = storage.Client(credentials=credentials)

    except HTTPException:
        raise
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Google Cloud/Firebase clients: {e}")
        raise HTTPException(status_code=500, detail="Could not connect to backend services.")

    # Fetch the expert tip document from Firestore
    tip_ref = db_firestore.collection("expert_tips").document(tip_id)
    tip_doc = tip_ref.get()

    if not tip_doc.exists:
        raise HTTPException(status_code=404, detail="Expert tip not found.")

    tip_data = tip_doc.to_dict()
    media_gcs_paths = tip_data.get("mediaUrls", [])

    if not media_gcs_paths:
        return SecureMediaUrlsResponse(secure_urls=[])

    secure_urls = []
    for gcs_path in media_gcs_paths:
        signed_url = _generate_signed_url(storage_client, gcs_path)
        if signed_url:
            secure_urls.append(signed_url)

    return SecureMediaUrlsResponse(secure_urls=secure_urls)
