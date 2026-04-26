# IMPORTANT: Import cache config FIRST to set UNSTRUCTURED_CACHE_DIR before unstructured library loads
import app.libs.cache_config  # noqa: F401 - side effect import to configure cache

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal, Union
import databutton as db
import traceback 
from google.cloud.storage import Client as StorageClient  # type: ignore
from google.cloud.vision import ImageAnnotatorClient  # type: ignore
from google.cloud.vision_v1.types import Feature, Image as GCVImage  # type: ignore
import tempfile
import os
import json
import imghdr
import uuid
import datetime
import re
import time
import asyncio
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from google.cloud.firestore import Client as FirestoreClient, SERVER_TIMESTAMP, Increment, FieldFilter, Query as FirestoreQuery  # type: ignore
from google.cloud.firestore import DocumentReference  # type: ignore
from google.oauth2 import service_account  # type: ignore
from google.cloud import storage as gcs  # type: ignore
import pinecone  # type: ignore
from pinecone import Pinecone, ServerlessSpec, NotFoundException  # type: ignore
import fitz  # type: ignore # PyMuPDF
from langchain_community.document_loaders import (  # type: ignore
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    UnstructuredImageLoader,
    CSVLoader,
    UnstructuredExcelLoader,
)
from PIL import Image
import base64
import io
import zipfile
from pathlib import Path
from unstructured.partition.auto import partition
from unstructured.chunking.basic import chunk_elements
from unstructured.documents.elements import (
    Image as UnstructuredImage
)
from unstructured.cleaners.core import clean_extra_whitespace

from app.auth import AuthorizedUser # Assuming this is in app/auth.py
from app.libs.user_utils import get_user_data, verify_admin_role

import requests
from google.cloud import tasks_v2 # NEW: Import Cloud Tasks client
from google.protobuf import duration_pb2  # <-- ADD THIS IMPORT
from datetime import timedelta
from urllib.parse import urlparse
# NEW: Import the optimized client getter
from app.libs.firebase_config import get_firestore_client, get_gcs_credentials
from app.libs.gemini_client import get_gemini_client

# --- Constants and Configuration ---
DEFAULT_GCS_BUCKET_NAME = "techtalk-document-images"
DOCUMENTS_GCS_BUCKET_NAME = "techtalk-documents"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
router = APIRouter()

# --- NEW: Cloud Tasks Configuration ---
# Ensure these secrets are set in your Databutton environment
CLOUD_TASKS_PROJECT_ID = "juniortechbot"
CLOUD_TASKS_LOCATION = "us-central1"
CLOUD_TASKS_QUEUE_NAME = "document-processing-queue"
WORKER_URL = f"https://riff.new/_projects/{CLOUD_TASKS_PROJECT_ID}/dbtn/prodx/app/routes/process-document-worker"

# --- Pydantic Models ---
class ProcessingProgress(BaseModel):
    stage: str
    progress: float
    message: str
    lastUpdated: Optional[str] = None

class DocumentStatus(BaseModel):
    status: str
    progress: Optional[ProcessingProgress] = None
    error: Optional[str] = None

class DocumentResponse(BaseModel):
    id: str
    title: str
    fileName: str
    fileType: str
    status: str
    company: str
    createdAt: str
    source: str  # e.g., "DASHBOARD_UPLOAD", "ZIP_IMPORT"
    jobId: Optional[str] = None
    description: Optional[str] = None
    isProcessed: bool = False
    tags: List[str] = []
    organization: Optional[str] = None
    fileSize: Optional[int] = None
    totalChunks: Optional[int] = None
    progress: Optional[ProcessingProgress] = None
    target_index: Optional[str] = None

class AdminMetrics(BaseModel):
    total_documents: int
    queued: int
    processing: int
    completed: int
    failed: int

class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    pagination: Dict[str, Any]
    message: Optional[str] = None
    error: Optional[str] = None
    
class DocumentMetricsSummary(BaseModel):
    document_count: int

# Document update model
class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, description="Document title")
    description: Optional[str] = Field(None, description="Document description")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    status: Optional[str] = Field(None, description="Document status")

# Define the response model
class SecureUrlResponse(BaseModel):
    signed_url: str

# --- Utility Functions ---
def convert_firestore_timestamps_to_strings(data: Union[Dict[str, Any], List[Any]]) -> Union[Dict[str, Any], List[Any]]:
    """
    Recursively converts native Firestore types (datetime, DocumentReference) 
    within a dictionary or list structure to ISO 8601 strings.
    
    This is necessary because Pydantic models typically define timestamp fields as 'str',
    but Firestore returns Python datetime objects after SERVER_TIMESTAMP is resolved, 
    causing validation errors in the API response.
    """
    if data is None:
        return None
        
    if isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            if isinstance(value, datetime.datetime):
                # Convert datetime objects to ISO 8601 string format
                new_data[key] = value.isoformat()
            elif isinstance(value, dict) or isinstance(value, list):
                # Recurse into nested structures (e.g., the 'progress' object)
                new_data[key] = convert_firestore_timestamps_to_strings(value)
            elif isinstance(value, DocumentReference):
                # Convert DocumentReference objects (if any) to their string path
                new_data[key] = value.path
            else:
                new_data[key] = value
        return new_data
        
    elif isinstance(data, list):
        # Handle lists by recursively checking each element
        new_list = []
        for item in data:
            new_list.append(convert_firestore_timestamps_to_strings(item))
        return new_list
            
    # Base case for primitive types
    return data

def get_user_data_from_firestore(user_id: str):
    """Get user data from Firestore using centralized client"""
    try:
        db_client = get_firestore_client()
        user_ref = db_client.collection('users').document(user_id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        return user_doc.to_dict()
    except Exception as e:
        print(f"Error getting user data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user data: {str(e)}")
        
def sanitize_storage_key(key: str) -> str:
    return re.sub(r'[^a-zA-Z0-9._-]', '', key)

def log_admin_action(user_data: dict, action: str, resource_type: str, resource_id: str, details: dict):
    try:
        db_client = get_firestore_client()
        audit_ref = db_client.collection('auditLogs').document()
        audit_data = {
            'id': audit_ref.id, 'timestamp': SERVER_TIMESTAMP, 'uid': user_data.get('uid'),
            'userEmail': user_data.get('email'), 'userRole': user_data.get('role'),
            'company': user_data.get('company'), 'action': action, 'resourceType': resource_type,
            'resourceId': resource_id, 'details': details
        }
        audit_ref.set(audit_data)
    except Exception as e:
        print(f"Error logging admin action: {e}")

# --- API Endpoints ---
@router.post("/upload-document")
async def upload_document(
    user: AuthorizedUser, 
    file: UploadFile = File(...), 
    title: str = Form(...), 
    description: Optional[str] = Form(None), 
    target_index: Optional[str] = Form("general"),
    tags: Optional[str] = Form(None)
):
    """Uploads a document, saves it to GCS, and enqueues a processing task."""
    try:
        # --- 1. Initial Validation and Setup ---
        db_client = get_firestore_client()
        if not db_client:
            raise HTTPException(status_code=500, detail="Server configuration error: Could not get Firestore client.")

        user_data = get_user_data_from_firestore(user.sub)
        if not verify_admin_role(user_data):
            raise HTTPException(status_code=403, detail="Only admins can upload documents")
        
        company = user_data.get('company') or "SYSTEM"
        
        # --- 2. Stream File to GCS Directly ---
        original_filename = file.filename
        unique_id = str(uuid.uuid4())

        # Sanitize the filename to prevent URL encoding issues
        safe_filename = re.sub(r'[\\/:\s]+', '_', original_filename)
                
        # This aligns the path with the multi-tenant structure used by the zip importer.
        gcs_path = f"companies/{company}/documents/{unique_id}/{safe_filename}"

        creds = get_gcs_credentials()
        storage_client = gcs.Client(credentials=creds)
        bucket = storage_client.bucket(DOCUMENTS_GCS_BUCKET_NAME)
        
        # Ensure the bucket exists
        if not bucket.exists():
            print(f"Bucket '{DOCUMENTS_GCS_BUCKET_NAME}' not found. Creating it now...")
            try:
                bucket = storage_client.create_bucket(bucket, location="US")
                print(f"Bucket '{DOCUMENTS_GCS_BUCKET_NAME}' created successfully.")
            except Exception as create_err:
                print(f"❌ Failed to create bucket '{DOCUMENTS_GCS_BUCKET_NAME}': {create_err}")
                raise HTTPException(status_code=500, detail=f"Failed to create GCS bucket: {create_err}")

        blob = bucket.blob(gcs_path)
        
        file_content_bytes = await file.read()
        file_size = len(file_content_bytes)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB")

        blob.upload_from_string(file_content_bytes, content_type=file.content_type)
        blob.make_public()
        file_url = blob.public_url

        # --- 3. Create Firestore Record (Status: 'queued') ---
        doc_ref = db_client.collection('documents').document(unique_id)
        tag_list = json.loads(tags) if tags and tags.startswith('[') else [t.strip() for t in (tags or "").split(',')]
        
        # Calculate totalPages for PDFs
        total_pages = 0
        if file.content_type == "application/pdf":
            try:
                with fitz.open(stream=file_content_bytes, filetype="pdf") as pdf_doc:
                    total_pages = pdf_doc.page_count
                print(f"📄 PDF detected. Found {total_pages} pages for document {unique_id}.")
            except Exception as pdf_err:
                print(f"⚠️ Could not read page count from PDF {original_filename}: {pdf_err}")

        doc_data = {
            'id': unique_id, 'title': title, 'description': description,
            'fileUrl': file_url, 'fileName': original_filename, 'fileType': file.content_type,
            'fileSize': file_size, 'uploadedBy': user.sub, 'company': company,
            'organization': company, 'uploadedAt': SERVER_TIMESTAMP,
            'status': 'queued', 'tags': tag_list, 'isProcessed': False,
            'totalPages': total_pages,
            'source': "DASHBOARD_UPLOAD",
            'target_index': target_index,
            'progress': {
                "stage": "queued",
                "message": "Document awaiting processing.",
                "progress": 0,
                "lastUpdated": SERVER_TIMESTAMP
            }
        }
        print(f"[UPLOAD_DEBUG] Saving to Firestore with target_index: '{target_index}'")
        doc_ref.set(doc_data)

        # --- 4. Enqueue Document Processing Task to Cloud Tasks ---
        try:
            creds = get_gcs_credentials()  # Uses GOOGLE_CLOUD_CREDENTIALS ✅
            tasks_client = tasks_v2.CloudTasksClient(credentials=creds)
            parent = tasks_client.queue_path(CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION, CLOUD_TASKS_QUEUE_NAME)

            # Create a JSON-serializable version of doc_data for the worker
            serializable_doc_data = doc_data.copy()
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
            serializable_doc_data['uploadedAt'] = now_iso
            if 'progress' in serializable_doc_data and isinstance(serializable_doc_data['progress'], dict):
                serializable_doc_data['progress']['lastUpdated'] = now_iso

            serializable_doc_data = convert_firestore_timestamps_to_strings(serializable_doc_data)
            
            # The payload sent to the worker endpoint
            worker_payload = {
                "doc_id": unique_id,
                "file_url": file_url,
                "doc_data": serializable_doc_data,
                "is_sub_document": False,
                "original_doc_id": unique_id,
                "target_index": target_index,
                "start_page_original": 1
            }

            task = {
                'http_request': {
                    'http_method': tasks_v2.HttpMethod.POST,
                    'url': "https://riff.new/_projects/24943f2a-846d-4587-b501-f26cc2851ea5/dbtn/prodx/app/routes/process-document-worker",
                    'headers': {'Content-type': 'application/json'},
                    'body': json.dumps(worker_payload).encode('utf-8')
                }
            }

            deadline = duration_pb2.Duration()
            deadline.seconds = 1800  # 30 minutes
            task['dispatch_deadline'] = deadline
           
            response = tasks_client.create_task(parent=parent, task=task)
            print(f"[API] Task enqueued to Cloud Tasks: {response.name}. Doc: {unique_id}")

        except Exception as tasks_e:
            print(f"❌ [API] Error enqueuing task to Cloud Tasks: {tasks_e}")
            traceback.print_exc()
            db_client.collection('documents').document(unique_id).update({
                "status": "failed",
                "lastError": f"Failed to enqueue processing task: {str(tasks_e)}",
                "failedAt": SERVER_TIMESTAMP
            })
            raise HTTPException(status_code=500, detail=f"Error processing document: Failed to enqueue processing task. {str(tasks_e)}")

        # --- 5. Log and Respond ---
        log_admin_action(user_data, 'upload_document', 'document', unique_id, {'title': title, 'fileName': original_filename})

        return DocumentResponse(
            id=unique_id, title=title, description=description,
            fileName=original_filename, fileType=file.content_type,
            status='queued', tags=tag_list, createdAt=datetime.datetime.now().isoformat(),
            company=company, organization=company, fileSize=file_size,
            source="DASHBOARD_UPLOAD",
            target_index=target_index,
            progress=ProcessingProgress(stage="queued", message="Document awaiting processing.", progress=0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"DETAILED ERROR in upload_document: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error uploading document: {str(e)}")


@router.get("/documents/{doc_id}/status")
async def get_document_status(doc_id: str, user: AuthorizedUser) -> DocumentStatus:
    try:
        user_data = get_user_data_from_firestore(user.sub)
        db_client = get_firestore_client()
        doc_ref = db_client.collection('documents').document(doc_id)
        doc_data = doc_ref.get()
        
        if not doc_data.exists:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc_dict = doc_data.to_dict()       
        
        if user_data.get('role') != 'system_admin' and doc_dict.get('company') != user_data.get('company'):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return DocumentStatus(
            status=doc_dict.get('status', 'unknown'),
            progress=doc_dict.get('progress'),
            error=doc_dict.get('lastError')
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving status: {e}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(user: AuthorizedUser, 
                       company: Optional[str] = None,
                       organization: Optional[str] = None,
                       status: Optional[str] = None,
                       search: Optional[str] = None,
                       jobId: Optional[str] = None,
                       limit: int = 50,
                       offset: int = 0):
    """List documents (admin only)"""
    
    try:
        # Get user data and verify admin role
        try:
            user_data = get_user_data_from_firestore(user.sub)
            
            if not verify_admin_role(user_data):
                return DocumentListResponse(
                    documents=[],
                    pagination={"total": 0, "limit": limit, "offset": offset, "hasMore": False},
                    message="Only admins can list documents"
                )
        except Exception as user_err:
            print(f"Error retrieving user data: {str(user_err)}")
            return DocumentListResponse(
                documents=[],
                pagination={"total": 0, "limit": limit, "offset": offset, "hasMore": False},
                message="User data not found or invalid"
            )
        
        # Initialize Firestore client
        try:
            db_client = get_firestore_client()
        except Exception as db_err:
            print(f"Error initializing Firestore client: {str(db_err)}")
            return DocumentListResponse(
                documents=[],
                pagination={"total": 0, "limit": limit, "offset": offset, "hasMore": False},
                message=f"Database connection error: {str(db_err)}"
            )
        
        # Set company filter based on user role
        user_role = user_data.get('role', '').lower()
        if 'company_admin' in user_role and 'system_admin' not in user_role:
            company = user_data.get('company')
            if not company:
                return DocumentListResponse(
                    documents=[],
                    pagination={"total": 0, "limit": limit, "offset": offset, "hasMore": False},
                    message="No company associated with this admin account"
                )
        
        # Build query
        query = db_client.collection('documents')

        # Apply filters
        if company:
            query = query.where(filter=FieldFilter('company', '==', company))
        
        if organization:
            query = query.where(filter=FieldFilter('organization', '==', organization))
        
        if jobId:
            query = query.where(filter=FieldFilter('jobId', '==', jobId))
                
        # Handle multiple statuses
        if status:
            status_list = [s.strip() for s in status.split(',')]
            if len(status_list) > 1:
                query = query.where(filter=FieldFilter('status', 'in', status_list))
            elif len(status_list) == 1:
                query = query.where(filter=FieldFilter('status', '==', status_list[0]))

        # Order by upload timestamp (descending)
        try:
            query = query.order_by('uploadedAt', direction=FirestoreQuery.DESCENDING)
        except Exception as order_err:
            print(f"Error applying order: {str(order_err)}")
            pass
        
        # Execute query
        try:
            docs = list(query.limit(limit).offset(offset).stream())
        except Exception as query_err:
            print(f"Error executing Firestore query: {str(query_err)}")
            return DocumentListResponse(
                documents=[],
                pagination={"total": 0, "limit": limit, "offset": offset, "hasMore": False},
                message=f"Error retrieving documents: {str(query_err)}"
            )
        
        # If no documents found, return empty results with proper pagination
        if not docs:
            search_terms = []
            if company: 
                search_terms.append(f"company '{company}'")
            if organization: 
                search_terms.append(f"organization '{organization}'")
            if status: 
                search_terms.append(f"status '{status}'")
            if search: 
                search_terms.append(f"search term '{search}'")
            
            message = "No documents found"
            if search_terms:
                message += f" matching {', '.join(search_terms)}"
                
            return DocumentListResponse(
                documents=[],
                pagination={"total": 0, "limit": limit, "offset": offset, "hasMore": False},
                message=message
            )
        
        # Convert to list of dictionaries
        results = []
        for doc in docs:
            try:
                doc_data = doc.to_dict()
                
                if not doc_data: continue

                doc_data = convert_firestore_timestamps_to_strings(doc_data)
                
                if search and not (search.lower() in doc_data.get('title', '').lower() or search.lower() in doc_data.get('description', '').lower()):
                    continue
                
                doc_data['createdAt'] = doc_data.get('uploadedAt', datetime.datetime.now(datetime.timezone.utc).isoformat())

                results.append(DocumentResponse(
                    id=doc.id,
                    title=doc_data.get('title', 'No Title'),
                    fileName=doc_data.get('fileName', 'N/A'),
                    fileType=doc_data.get('fileType', 'N/A'),
                    status=doc_data.get('status', 'unknown'),
                    company=doc_data.get('company', 'N/A'),
                    createdAt=doc_data['createdAt'],
                    source=doc_data.get('source', 'unknown'),
                    jobId=doc_data.get('jobId'),
                    description=doc_data.get('description'),
                    isProcessed=doc_data.get('isProcessed', False),
                    tags=doc_data.get('tags', []),
                    organization=doc_data.get('organization'),
                    fileSize=doc_data.get('fileSize'),
                    totalChunks=doc_data.get('totalChunks'),
                    progress=doc_data.get('progress')
                ))
            except Exception as doc_err:
                print(f"Error processing document {doc.id}: {str(doc_err)}")
                continue
        
        # Handle case where all documents were filtered out by search
        if not results and search:
            return DocumentListResponse(
                documents=[],
                pagination={"total": 0, "limit": limit, "offset": offset, "hasMore": False},
                message=f"No documents found matching search term '{search}'"
            )
        
        # Get total count (for pagination)
        try:
            count_query = db_client.collection('documents')
            if company:
                count_query = count_query.where(filter=FieldFilter('company', '==', company))
            if organization:
                count_query = count_query.where(filter=FieldFilter('organization', '==', organization))
            if status:
                status_list = [s.strip() for s in status.split(',')]
                if len(status_list) > 1:
                    count_query = count_query.where(filter=FieldFilter('status', 'in', status_list))
                elif len(status_list) == 1:
                    count_query = count_query.where(filter=FieldFilter('status', '==', status_list[0]))

            total_count = sum(1 for _ in count_query.stream())
        except Exception as count_err:
            print(f"Error getting total count: {str(count_err)}")
            total_count = len(results)
        
        return DocumentListResponse(
            documents=results,
            pagination={
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "hasMore": offset + len(results) < total_count
            }
        )
        
    except Exception as e:
        print(f"CRITICAL ERROR in list_documents: {e}")
        traceback.print_exc()
        return DocumentListResponse(
            documents=[],
            pagination={"total": 0, "limit": limit, "offset": offset, "hasMore": False},
            error=str(e),
            message="An error occurred while retrieving documents"
        )


@router.get("/document-metrics-summary", response_model=DocumentMetricsSummary)
async def get_document_metrics_summary(user: AuthorizedUser):
    """Provides a document count summary for a company admin."""
    
    try:
        user_data = get_user_data_from_firestore(user.sub)
        if not verify_admin_role(user_data):
            raise HTTPException(status_code=403, detail="Unauthorized")

        company = user_data.get("company")
        if not company:
            raise HTTPException(status_code=400, detail="User not associated with a company")

        db_client = get_firestore_client()
        docs_ref = db_client.collection('documents')
        docs_query = docs_ref.where('company', '==', company).stream()
        count = sum(1 for _ in docs_query)
        
        return DocumentMetricsSummary(document_count=count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting metrics: {e}")


@router.get("/documents/{doc_id}/get_document_optimal")
async def get_document_optimal(doc_id: str, user: AuthorizedUser) -> DocumentResponse:
    """
    Optimized version of get_document.
    Uses a global Firestore client to avoid re-initialization and disk I/O on every call.
    """
    try:
        db_client = get_firestore_client()
        user_data = get_user_data_from_firestore(user.sub)

        doc_ref = db_client.collection('documents').document(doc_id)
        doc_data = doc_ref.get()
        
        if not doc_data.exists:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc_dict = doc_data.to_dict()
        doc_dict = convert_firestore_timestamps_to_strings(doc_dict)
        
        if user_data.get('role') != 'system_admin' and doc_dict.get('company') != user_data.get('company'):
            raise HTTPException(status_code=403, detail="Access denied")
        
        doc_dict['createdAt'] = doc_dict.get('uploadedAt', datetime.datetime.now(datetime.timezone.utc).isoformat())
        doc_dict['description'] = doc_dict.get('description')
        doc_dict['tags'] = doc_dict.get('tags', [])
        doc_dict['organization'] = doc_dict.get('organization', doc_dict.get('company'))
        doc_dict['fileSize'] = doc_dict.get('fileSize')
        doc_dict['totalChunks'] = doc_dict.get('totalChunks')
        doc_dict['progress'] = doc_dict.get('progress')
        doc_dict['status'] = doc_dict.get('status', 'unknown')
        doc_dict['isProcessed'] = doc_dict.get('isProcessed', False)

        return DocumentResponse(**doc_dict)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error in optimal document retrieval: {e}")


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, user: AuthorizedUser) -> DocumentResponse:
    try:
        user_data = get_user_data_from_firestore(user.sub)
        db_client = get_firestore_client()
        doc_ref = db_client.collection('documents').document(doc_id)
        doc_data = doc_ref.get()
        
        if not doc_data.exists:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc_dict = doc_data.to_dict()
        doc_dict = convert_firestore_timestamps_to_strings(doc_dict)
        
        if user_data.get('role') != 'system_admin' and doc_dict.get('company') != user_data.get('company'):
            raise HTTPException(status_code=403, detail="Access denied")
        
        doc_dict['createdAt'] = doc_dict.get('uploadedAt', datetime.datetime.now(datetime.timezone.utc).isoformat())
        doc_dict['description'] = doc_dict.get('description')
        doc_dict['tags'] = doc_dict.get('tags', [])
        doc_dict['organization'] = doc_dict.get('organization', doc_dict.get('company'))
        doc_dict['fileSize'] = doc_dict.get('fileSize')
        doc_dict['totalChunks'] = doc_dict.get('totalChunks')
        doc_dict['progress'] = doc_dict.get('progress')
        doc_dict['status'] = doc_dict.get('status', 'unknown')
        doc_dict['isProcessed'] = doc_dict.get('isProcessed', False)

        return DocumentResponse(**doc_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving document: {e}")


@router.get("/get-secure-document-url/{document_id}", response_model=SecureUrlResponse)
async def get_secure_document_url(document_id: str, user: AuthorizedUser):
    """
    Generates a secure, short-lived URL to view a document.
    """
    
    try:
        user_data = get_user_data_from_firestore(user.sub)
                
        firestore_client = get_firestore_client()
        creds = get_gcs_credentials()
        storage_client = StorageClient(credentials=creds)

        doc_ref = firestore_client.collection("documents").document(document_id)
        doc_snapshot = doc_ref.get()

        if not doc_snapshot.exists:
            raise HTTPException(status_code=404, detail="Document not found.")

        doc_data = doc_snapshot.to_dict()
        
        # Check if the user's company matches the document's company
        if user_data.get('company') != doc_data.get('company') and user_data.get('role') != 'system_admin':
            raise HTTPException(status_code=403, detail="Access denied. User does not have permission for this document.")

        file_url = doc_data.get("fileUrl")
        if not file_url:
            raise HTTPException(
                status_code=400, 
                detail="Document record is missing the required fileUrl."
            )
            
        # Extract the file path from the full URL
        try:
            parsed_url = urlparse(file_url)
            file_path = parsed_url.path.lstrip('/')
            
            if file_path.startswith(DOCUMENTS_GCS_BUCKET_NAME + '/'):
                file_path = file_path[len(DOCUMENTS_GCS_BUCKET_NAME) + 1:]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid fileUrl format.")

        # Generate the signed URL
        bucket_name = DOCUMENTS_GCS_BUCKET_NAME
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_path)

        signed_url = blob.generate_signed_url(expiration=timedelta(minutes=15))
        
        return SecureUrlResponse(signed_url=signed_url)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Error generating secure URL for doc {document_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Could not generate secure URL.")


@router.put("/documents/{document_id}")
async def update_document(document_id: str, 
                        request: DocumentUpdateRequest,
                        user: AuthorizedUser):
    """Update document metadata (admin only)"""
    
    try:
        user_data = get_user_data_from_firestore(user.sub)
        
        if not verify_admin_role(user_data):
            raise HTTPException(status_code=403, detail="Only admins can update documents")
        
        db_client = get_firestore_client()
        
        doc_ref = db_client.collection('documents').document(document_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Document not found")
        
        doc_data = doc.to_dict()
        
        # Check company access for company admins
        if user_data.get('role') == 'company_admin' and doc_data.get('company') != user_data.get('company'):
            raise HTTPException(status_code=403, detail="Access denied to document from another company")
        
        # Prepare update data
        update_data = {}
        if request.title is not None:
            update_data['title'] = request.title
        if request.description is not None:
            update_data['description'] = request.description
        if request.tags is not None:
            update_data['tags'] = request.tags
        if request.status is not None:
            update_data['status'] = request.status
        
        # Only allow status updates if the document is not in processing state
        if request.status is not None and doc_data.get('status') == 'processing' and request.status != 'archived':
            raise HTTPException(status_code=400, detail="Cannot update status of a document in processing state")
        
        update_data['lastModified'] = SERVER_TIMESTAMP
        
        doc_ref.update(update_data)
        
        log_admin_action(
            user_data=user_data,
            action='update_document',
            resource_type='document',
            resource_id=document_id,
            details=update_data
        )
        
        updated_doc = doc_ref.get().to_dict()       
        
        # Convert timestamps to ISO format
        if 'uploadedAt' in updated_doc and isinstance(updated_doc['uploadedAt'], datetime.datetime):
            updated_doc['uploadedAt'] = updated_doc['uploadedAt'].isoformat()
            
        if 'lastModified' in updated_doc and isinstance(updated_doc['lastModified'], datetime.datetime):
            updated_doc['lastModified'] = updated_doc['lastModified'].isoformat()
            
        if 'moderationDetails' in updated_doc and 'moderatedAt' in updated_doc['moderationDetails'] \
            and isinstance(updated_doc['moderationDetails']['moderatedAt'], datetime.datetime):
            updated_doc['moderationDetails']['moderatedAt'] = updated_doc['moderationDetails']['moderatedAt'].isoformat()
        
        return updated_doc
        
    except Exception as e:
        print(f"Error updating document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating document: {str(e)}")


# --- Deletion Helper Functions ---
def get_pinecone_client(api_key):
    """Initialize and return Pinecone client"""
    try:
        return Pinecone(api_key=api_key)
    except Exception as e:
        print(f"Error initializing Pinecone: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Vector database connection error: {str(e)}")

def _delete_gcs_ExtractedImagesfolder(company_id: str, doc_id: str):
    """
    Deletes all objects in GCS under a document's specific folder prefix.
    """
    prefix = f"companies/{company_id}/documents/{doc_id}/"
    
    print(f"☁️ Starting GCS recursive delete for prefix: {prefix}")

    if not company_id or not doc_id:
        print(f"⚠️ GCS folder delete skipped for prefix '{prefix}': Missing company_id or doc_id.")
        return

    try:
        creds = get_gcs_credentials()
        storage_client = StorageClient(credentials=creds)
        bucket = storage_client.bucket(DEFAULT_GCS_BUCKET_NAME)

        blobs_to_delete = list(bucket.list_blobs(prefix=prefix))

        if not blobs_to_delete:
            print(f"✅ No GCS files found for prefix '{prefix}'. Nothing to delete.")
            return
            
        print(f"  - Found {len(blobs_to_delete)} files to delete.")

        for blob in blobs_to_delete:
            try:
                blob.delete()
            except Exception as blob_delete_err:
                print(f"  - ❌ Failed to delete blob {blob.name}: {blob_delete_err}")
        
        print(f"✅ Successfully deleted {len(blobs_to_delete)} GCS files for prefix '{prefix}'.")

    except Exception as e:
        print(f"❌ A critical error occurred during GCS folder deletion for prefix '{prefix}': {e}")
        traceback.print_exc()

def _delete_from_pinecone(doc_id: str, company_id: str, target_index: str):
    """Deletes all vectors (text and image) associated with a document ID from the company's Pinecone indices."""
    if not company_id:
        print(f"⚠️ Pinecone delete skipped for doc '{doc_id}': Missing company_id.")
        return
        
    print(f"🌲 Starting Pinecone deletion for doc_id: {doc_id} in company: {company_id}")
    try:
        pinecone_api_key = os.environ.get("PINECONE_API_KEY")
        if not pinecone_api_key:
            print("❌ Pinecone API key not configured. Skipping deletion.")
            return

        pinecone_client = get_pinecone_client(pinecone_api_key)
            
        sanitized_company_id = company_id.lower().replace('_', '-')
        sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index).lower()
        index_names_to_check = [
            f"techtalk-text-{sanitized_company_id}",
            f"techtalk-image-{sanitized_company_id}"
        ]
        namespace = f"{sanitized_company_id}-{sanitized_target_index}"
        
        existing_indexes = [index.name for index in pinecone_client.list_indexes()]

        for index_name in index_names_to_check:
            print(f"🌲 Checking index: {index_name}")
            
            if index_name not in existing_indexes:
                print(f"⚠️ Pinecone index '{index_name}' not found. Skipping.")
                continue

            print(f"  -> Index '{index_name}' found. Proceeding with deletion...")
            index = pinecone_client.Index(index_name)
                
            try:
                delete_response = index.delete(
                    filter={"document_id": {"$eq": doc_id}},
                    namespace=namespace
                )
                print(f"  ✅ Pinecone deletion response for index '{index_name}': {delete_response}")
            except NotFoundException:
                # Namespace doesn't exist - this is expected when no vectors were added
                print(f"  ℹ️ Namespace '{namespace}' not found in index '{index_name}'. Nothing to delete (expected for documents without images in image index).")
            except Exception as delete_err:
                # Actual error
                print(f"  ❌ FAILED to run delete on index '{index_name}': {delete_err}")

    except Exception as e:
        print(f"❌ FAILED to delete from Pinecone for doc '{doc_id}': {e}")
        traceback.print_exc()

def _delete_from_gcs(file_url: str, company_id: str, doc_id: str):
    """Deletes the main document file AND cleans up the entire document folder from GCS."""
    if not file_url or not file_url.startswith("https://storage.googleapis.com/"):
        print(f"⚠️ GCS delete skipped: Invalid or missing file_url ('{file_url}').")
        return

    print(f"☁️ Starting GCS deletion for URL: {file_url}")
    try:
        parts = file_url.replace("https://storage.googleapis.com/", "").split("/", 1)
        if len(parts) < 2:
            print(f"❌ Could not parse bucket/blob from GCS URL: {file_url}")
            return
                
        bucket_name, blob_name = parts
        
        creds = get_gcs_credentials()
        storage_client = StorageClient(credentials=creds)
        bucket = storage_client.bucket(bucket_name)
        
        # Delete the main file first
        blob = bucket.blob(blob_name)
        if blob.exists():
            blob.delete()
            print(f"✅ Successfully deleted main GCS blob: {blob_name} from bucket: {bucket_name}")
        else:
            print(f"⚠️ Main GCS blob not found, skipping: {blob_name}")
        
        # Clean up the entire document folder
        if company_id and doc_id:
            prefix = f"companies/{company_id}/documents/{doc_id}/"
            blobs_to_delete = list(bucket.list_blobs(prefix=prefix))
            
            if blobs_to_delete:
                print(f"  - Found {len(blobs_to_delete)} additional file(s) in folder '{prefix}' to delete.")
                for remaining_blob in blobs_to_delete:
                    try:
                        remaining_blob.delete()
                        print(f"  - ✅ Deleted: {remaining_blob.name}")
                    except Exception as e:
                        print(f"  - ❌ Failed to delete {remaining_blob.name}: {e}")
                print(f"✅ Successfully cleaned up document folder: {prefix}")
            else:
                print(f"  - No additional files found in folder '{prefix}'. Folder cleanup complete.")

    except Exception as e:
        print(f"❌ FAILED to delete from GCS for URL '{file_url}': {e}")
        traceback.print_exc()


@router.delete("/documents/{doc_id}", status_code=204)
async def delete_document(doc_id: str, user: AuthorizedUser):
    """
    Deletes a document and its associated data from Firestore, GCS, and Pinecone.
    This is a permanent action.
    """
    try:
        user_data = get_user_data_from_firestore(user.sub)
        if not verify_admin_role(user_data):
            raise HTTPException(status_code=403, detail="You are not authorized to delete documents.")

        db_client = get_firestore_client()
        doc_ref = db_client.collection('documents').document(doc_id)
        doc_snapshot = doc_ref.get()

        if not doc_snapshot.exists:
            print(f"Document {doc_id} not found in Firestore. Assuming already deleted.")
            return

        doc_data = doc_snapshot.to_dict()
        company_id = doc_data.get('company')
        target_index = doc_data.get('target_index', 'general')
        file_url = doc_data.get('fileUrl')

        # Perform Deletions in Parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            executor.submit(_delete_from_pinecone, doc_id, company_id, target_index)
            executor.submit(_delete_from_gcs, file_url, company_id, doc_id)
            executor.submit(_delete_gcs_ExtractedImagesfolder, company_id, doc_id)
                
        # Delete from Firestore
        if user_data.get('role') == 'company_admin' and user_data.get('company') != company_id:
            raise HTTPException(status_code=403, detail="You can only delete documents from your own company.")
            
        doc_ref.delete()
        print(f"✅ Successfully deleted Firestore document: {doc_id}")

        # Log Action
        log_admin_action(
            user_data, 'delete_document', 'document', doc_id, 
            {'title': doc_data.get('title', 'N/A'), 'fileName': doc_data.get('fileName', 'N/A')}
        )
            
        return

    except Exception as e:
        print(f"❌ CRITICAL ERROR in delete_document for doc_id '{doc_id}': {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
