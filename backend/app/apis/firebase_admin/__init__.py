import firebase_admin
from firebase_admin import credentials, firestore, auth as firebase_auth, exceptions as firebase_exceptions
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

import databutton as db
import json
import os

# Use centralized lazy Firebase initialization
from app.libs.firebase_config import get_firestore_client, get_storage_bucket

router = APIRouter()

# Firebase Admin SDK is now initialized centrally in src/main.py.
# The global variables and initialization functions are no longer needed here.

class FirebaseStatusResponse(BaseModel):
    initialized: bool
    message: str
    project_id: Optional[str] = None
    default_app_name: Optional[str] = None

@router.get("/status", response_model=FirebaseStatusResponse)
async def firebase_status():
    """Checks the status of Firebase Admin SDK initialization."""
    # Trigger lazy initialization by getting client
    try:
        db_firestore = get_firestore_client()
        if db_firestore:
            # Firebase is initialized
            default_app = firebase_admin.get_app()
            project_id = default_app.project_id
            return FirebaseStatusResponse(
                initialized=True, 
                message="Firebase Admin SDK is initialized.",
                project_id=project_id,
                default_app_name=default_app.name
            )
    except Exception as e:
        return FirebaseStatusResponse(
            initialized=False, 
            message=f"Firebase Admin SDK initialization error: {str(e)}"
        )
    
    return FirebaseStatusResponse(
        initialized=False, 
        message="Firebase Admin SDK is NOT initialized."
    )
