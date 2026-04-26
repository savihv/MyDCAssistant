"""Centralized Firebase configuration with lazy initialization and production environment cleanup.

This module provides singleton Firebase clients that are initialized on first use (lazy),
ensuring that:
1. Secrets are available when initialization happens (at request time, not import time)
2. Production environment is cleaned of emulator variables before initialization
3. All API files use the same Firebase instance (singleton pattern)
4. Thread-safe initialization
"""

import os
import threading
import json
import firebase_admin
from firebase_admin import credentials, firestore as fb_admin_firestore, storage as fb_admin_storage
from app.env import mode, Mode
from typing import Optional
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.storage import Bucket
from google.oauth2 import service_account

# Global state - initialized to None, will be set on first use
_firebase_initialized = False
_db_firestore: Optional[FirestoreClient] = None
_storage_bucket: Optional[Bucket] = None
_init_lock = threading.Lock()

# Firebase Storage bucket name
FIREBASE_BUCKET_NAME = "juniortechbot.firebasestorage.app"

def _cleanup_emulator_variables():
    """Remove Firebase emulator environment variables in production."""
    if mode == Mode.PROD:
        emulator_vars = [
            'FIRESTORE_EMULATOR_HOST',
            'FIREBASE_AUTH_EMULATOR_HOST',
            'FIREBASE_DATABASE_EMULATOR_HOST',
            'FIREBASE_STORAGE_EMULATOR_HOST',
        ]
        
        for var in emulator_vars:
            if var in os.environ:
                removed_value = os.environ.pop(var)
                print(f"INFO [firebase_config]: Removed emulator variable {var}={removed_value} (production mode)")
        
        print("INFO [firebase_config]: Production environment verified - no emulator variables present")
    else:
        print("INFO [firebase_config]: Development mode - emulator variables allowed")

def _initialize_firebase():
    """Internal function to perform actual Firebase initialization.
    
    This runs only once, on first use, in a thread-safe manner.
    """
    global _firebase_initialized, _db_firestore, _storage_bucket
    
    print(f"INFO [firebase_config]: Starting Firebase initialization (mode={mode})")
    
    # Step 1: Clean up emulator variables if in production
    _cleanup_emulator_variables()
    
    # Step 2: Check if Firebase Admin SDK is already initialized
    if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
        print("INFO [firebase_config]: Firebase Admin SDK default app already initialized")
        try:
            _db_firestore = fb_admin_firestore.client()
            _storage_bucket = fb_admin_storage.bucket(name=FIREBASE_BUCKET_NAME)
            _firebase_initialized = True
            print("INFO [firebase_config]: Reusing existing Firebase clients")
            return
        except Exception as e:
            print(f"ERROR [firebase_config]: Failed to get clients from existing app: {e}")
            # Continue to try initialization
    
    # Step 3: Initialize Firebase Admin SDK
    try:
        creds_json_str = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
        if not creds_json_str:
            raise ValueError("FIREBASE_ADMIN_CREDENTIALS secret not found")
        
        creds_dict = json.loads(creds_json_str)
        cred = credentials.Certificate(creds_dict)
        
        init_options = {
            'storageBucket': FIREBASE_BUCKET_NAME
        }
        project_id_from_creds = creds_dict.get('project_id')
        if project_id_from_creds:
            init_options['projectId'] = project_id_from_creds
        
        firebase_admin.initialize_app(cred, init_options)
        print(f"INFO [firebase_config]: Firebase Admin SDK initialized with options: {init_options}")
        
    except ValueError as e:
        if "already initialized" in str(e).lower() or "already exists" in str(e).lower():
            print("INFO [firebase_config]: Firebase Admin SDK already initialized (caught ValueError)")
        else:
            raise
    except Exception as e:
        print(f"ERROR [firebase_config]: Failed to initialize Firebase Admin SDK: {e}")
        raise
    
    # Step 4: Create clients
    try:
        _db_firestore = fb_admin_firestore.client()
        _storage_bucket = fb_admin_storage.bucket(name=FIREBASE_BUCKET_NAME)
        _firebase_initialized = True
        print("INFO [firebase_config]: Firebase clients created successfully")
        print(f"INFO [firebase_config]: Firestore client: {_db_firestore}")
        print(f"INFO [firebase_config]: Storage bucket: {_storage_bucket}")
    except Exception as e:
        print(f"ERROR [firebase_config]: Failed to create Firebase clients: {e}")
        raise

def get_firestore_client():
    """Get the Firestore client, initializing on first call.
    
    Returns:
        google.cloud.firestore.Client: The Firestore client instance
        
    Raises:
        Exception: If Firebase initialization fails
    """
    global _firebase_initialized, _db_firestore
    
    if _db_firestore is not None:
        return _db_firestore
    
    # Thread-safe initialization
    with _init_lock:
        # Double-check after acquiring lock
        if _db_firestore is not None:
            return _db_firestore
        
        _initialize_firebase()
        
        if _db_firestore is None:
            raise RuntimeError("Firebase initialization completed but Firestore client is None")
        
        return _db_firestore

def get_storage_bucket():
    """Get the Firebase Storage bucket, initializing on first call.
    
    Returns:
        google.cloud.storage.Bucket: The Firebase Storage bucket instance
        
    Raises:
        Exception: If Firebase initialization fails
    """
    global _firebase_initialized, _storage_bucket
    
    if _storage_bucket is not None:
        return _storage_bucket
    
    # Thread-safe initialization
    with _init_lock:
        # Double-check after acquiring lock
        if _storage_bucket is not None:
            return _storage_bucket
        
        _initialize_firebase()
        
        if _storage_bucket is None:
            raise RuntimeError("Firebase initialization completed but Storage bucket is None")
        
        return _storage_bucket

def get_firebase_credentials_dict():
    """Get Firebase credentials as a dictionary for direct Google Cloud client usage.
    
    This is useful for API files that need to create their own Google Cloud clients
    (e.g., for Firestore or GCS) rather than using Firebase Admin SDK.
    
    Returns:
        dict: The Firebase service account credentials as a dictionary
    """
    creds_json_str = os.environ.get("FIREBASE_ADMIN_CREDENTIALS")
    if not creds_json_str:
        raise ValueError("FIREBASE_ADMIN_CREDENTIALS secret not found")
    return json.loads(creds_json_str)

def get_gcs_credentials():
    """Get Google Cloud Storage credentials object.
    
    This uses GOOGLE_CLOUD_CREDENTIALS which has the necessary permissions for:
    - Cloud Tasks (Enqueuer role)
    - GCS operations (Storage Admin role)
    - Vertex AI (Vertex AI User role)
    
    Returns:
        google.oauth2.service_account.Credentials: GCS credentials
    """
    creds_json_str = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
    if not creds_json_str:
        raise ValueError("GOOGLE_CLOUD_CREDENTIALS secret not found")
    creds_dict = json.loads(creds_json_str)
    return service_account.Credentials.from_service_account_info(creds_dict)

def get_gcs_credentials_json():
    """Get Google Cloud Storage credentials as a JSON string.
    
    This is useful for passing credentials to workers or other services
    that need to reconstruct the credentials object.
    
    Returns:
        str: The GCS service account credentials as a JSON string
    """
    creds_json_str = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
    if not creds_json_str:
        raise ValueError("GOOGLE_CLOUD_CREDENTIALS secret not found")
    return creds_json_str

def get_gcs_project_id():
    """Get the GCP project ID from credentials."""
    creds_json_str = os.environ.get("GOOGLE_CLOUD_CREDENTIALS")
    if not creds_json_str:
        raise ValueError("GOOGLE_CLOUD_CREDENTIALS secret not found")
    creds_dict = json.loads(creds_json_str)
    return creds_dict.get('project_id')
    
def get_firestore_client_direct():
    """Get a Firestore client using direct Google Cloud SDK (not Firebase Admin SDK).
    
    This creates a new client instance each time. Use get_firestore_client() instead
    for better performance (singleton pattern).
    
    Returns:
        google.cloud.firestore.Client: A Firestore client instance
    """
    credentials = get_gcs_credentials()
    return FirestoreClient(credentials=credentials)
