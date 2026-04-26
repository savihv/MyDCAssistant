from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import databutton as db
import traceback
from google.cloud.storage import Client as StorageClient  # type: ignore
from google.oauth2 import service_account  # type: ignore
from google.cloud import storage as gcs  # type: ignore
from google.cloud.firestore import SERVER_TIMESTAMP  # type: ignore
import tempfile
import os
import json
import uuid
import zipfile
import datetime
from datetime import timezone, timedelta
import mimetypes
import re
import shutil

from app.auth import AuthorizedUser
from app.apis.document_management import DocumentResponse, convert_firestore_timestamps_to_strings
from app.libs.firebase_config import get_firestore_client, get_gcs_credentials
from google.cloud import tasks_v2  # type: ignore
from google.protobuf import duration_pb2  # type: ignore
import fitz  # type: ignore

router = APIRouter(prefix="/zip-importer", tags=["Zip Importer"])

# --- Constants ---
DOCUMENTS_GCS_BUCKET_NAME = "techtalk-documents"
PROJECT_ID = "24943f2a-846d-4587-b501-f26cc2851ea5"

# Cloud Tasks Configuration (matches document_management)
CLOUD_TASKS_PROJECT_ID = "juniortechbot"
CLOUD_TASKS_LOCATION = "us-central1"
CLOUD_TASKS_QUEUE_NAME = "document-processing-queue"
WORKER_URL = f"https://riff.new/_projects/{PROJECT_ID}/dbtn/prodx/app/routes/process-document-worker"

# --- Pydantic Models ---
class ZipUploadResponse(BaseModel):
    message: str
    job_id: str
    documents: List[DocumentResponse]


# --- Overhauled API Endpoint ---
@router.post("/upload", response_model=ZipUploadResponse)
async def upload_zip_archive(
    user: AuthorizedUser,
    companyId: str = Form(...),
    file: UploadFile = File(...),
    target_index: str = Form("general")
):
    print("[ZIP_IMPORTER_DEBUG] --- 1. Entered upload_zip_archive endpoint ---")
    job_id = str(uuid.uuid4())
    
    # Initialize zip_path for the finally block
    zip_path = None 
    
    created_documents = []
    
    print("[ZIP_IMPORTER_DEBUG] --- 2. Initializing Firebase clients ---")
    
    try:
        db_client = get_firestore_client()
        batch = db_client.batch()
        
        # ✅ CORRECT - Use GCS credentials for GCS operations
        creds = get_gcs_credentials()
        storage_client = gcs.Client(credentials=creds)
        bucket = storage_client.bucket(DOCUMENTS_GCS_BUCKET_NAME)
        
        # Initialize Cloud Tasks client with credentials
        tasks_client = tasks_v2.CloudTasksClient(credentials=creds)
        parent = tasks_client.queue_path(CLOUD_TASKS_PROJECT_ID, CLOUD_TASKS_LOCATION, CLOUD_TASKS_QUEUE_NAME)
        
        files_processed_count = 0
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize Google Cloud clients: {e}")

    print("[ZIP_IMPORTER_DEBUG] --- 3. Firestore and GCS clients initialized ---")

    try:
        # Copy uploaded file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_zip_file:
            shutil.copyfileobj(file.file, tmp_zip_file)
            zip_path = tmp_zip_file.name

        print(f"[ZIP_IMPORTER_DEBUG] --- 4. Copied uploaded file to temporary path: {zip_path} ---")

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for zip_info in zip_ref.infolist():
                if zip_info.is_dir() or zip_info.filename.startswith('__MACOSX/') or zip_info.filename.endswith('.DS_Store'):
                    continue

                filename = os.path.basename(zip_info.filename)
                original_doc_id = str(uuid.uuid4())
                safe_filename = re.sub(r'[\\/:\s]+', '_', filename)
                filename = safe_filename
                
                # --- SCHEMA FIX: Construct full public URL and get file metadata ---
                gcs_path = f"companies/{companyId}/documents/{original_doc_id}/{filename}"
                file_url = f"https://storage.googleapis.com/{DOCUMENTS_GCS_BUCKET_NAME}/{gcs_path}"
                blob = bucket.blob(gcs_path)
                
                # Manually determine the file type based on extension
                file_type = None
                if filename.lower().endswith('.rtf'):
                    file_type = 'text/rtf'
                elif filename.lower().endswith('.pdf'):
                    file_type = 'application/pdf'
                elif filename.lower().endswith('.py'):
                    file_type = 'text/x-python'
                elif filename.lower().endswith('.tf'):
                    file_type = 'text/x-terraform'
                elif filename.lower().endswith(('.yml', '.yaml')):
                    file_type = 'text/x-yaml'
                elif filename.lower().endswith('.json'):
                    file_type = 'application/json'
                elif filename.lower().endswith(('.c', '.h')):
                    file_type = 'text/x-c'
                elif filename.lower().endswith(('.cpp', '.hpp', '.cc', '.cxx')):
                    file_type = 'text/x-c++'
                elif filename.lower().endswith(('.txt', '.md')):
                    file_type = 'text/plain'
                else:
                    # Use mimetype as a fallback for other types
                    mime_type_guess, _ = mimetypes.guess_type(filename)
                    file_type = mime_type_guess or 'application/octet-stream' # Default if guess fails
                # --- END SCHEMA FIX ---

                # Calculate totalPages for PDFs (matching document_management logic)
                total_pages = 0
                if file_type == 'application/pdf':
                    try:
                        # Read PDF content from zip to count pages
                        with zip_ref.open(zip_info.filename) as file_in_zip:
                            pdf_bytes = file_in_zip.read()
                            with fitz.open(stream=pdf_bytes, filetype="pdf") as pdf_doc:
                                total_pages = pdf_doc.page_count
                            print(f"📄 PDF detected. Found {total_pages} pages for {filename}.")
                    except Exception as pdf_err:
                        print(f"⚠️ Could not read page count from PDF {filename}: {pdf_err}")

                # Upload to GCS (re-open from zip since we read it above for counting)
                with zip_ref.open(zip_info.filename) as file_in_zip:
                    blob.upload_from_file(file_in_zip, content_type=file_type)
                print(f"[ZIP_IMPORTER_DEBUG] --- 5. Uploaded {filename} to {file_url} ---")

                # Create document in Firestore with the CORRECTED schema
                doc_ref = db_client.collection('documents').document(original_doc_id)
                
                # --- SCHEMA FIX: Rebuild doc_data to match the document_management schema ---
                doc_data = {
                    'id': original_doc_id,
                    'title': filename,
                    'description': f"Uploaded via Zip Import job {job_id}",
                    'fileUrl': file_url,
                    'fileName': filename,
                    'fileType': file_type,
                    'fileSize': zip_info.file_size,
                    'uploadedBy': user.sub,
                    'company': companyId,
                    'organization': companyId, # CRITICAL: Add organization
                    'uploadedAt': SERVER_TIMESTAMP,
                    'status': 'queued',
                    'tags': ['zip-import', job_id],
                    'isProcessed': False,
                    'totalPages': total_pages, # Now set to actual page count for PDFs, 0 for others
                    'source': "ZIP_IMPORT",
                    'target_index': target_index,
                    'jobId': job_id,
                    'progress': { # Initialize progress object
                        "stage": "queued",
                        "message": "Document awaiting processing.",
                        "progress": 0,
                        "lastUpdated": SERVER_TIMESTAMP
                    }
                }
                # --- END SCHEMA FIX ---
                batch.set(doc_ref, doc_data)

                # Create a serializable copy for the API response
                response_doc_data = doc_data.copy()
                now_iso_string = datetime.datetime.now(timezone.utc).isoformat()
                
                # Replace ALL timestamp sentinels with a string
                response_doc_data["uploadedAt"] = now_iso_string
                if 'progress' in response_doc_data and isinstance(response_doc_data['progress'], dict):
                    response_doc_data['progress']['lastUpdated'] = now_iso_string

                # Use the new helper function to create a serializable copy for the API response
                response_doc_data = convert_firestore_timestamps_to_strings(response_doc_data)
                
                # The response model expects `createdAt`, so we rename the key for the response only
                if "uploadedAt" in response_doc_data:
                    response_doc_data["createdAt"] = response_doc_data.pop("uploadedAt")
                created_documents.append(DocumentResponse(**response_doc_data))

                # --- Create a JSON-serializable version of doc_data for the worker ---
                serializable_doc_data = doc_data.copy()
                # Use a consistent, serializable timestamp for the worker payload
                now_iso = datetime.datetime.now(timezone.utc).isoformat()
            
                # Replace the Sentinel values with a serializable string
                serializable_doc_data['uploadedAt'] = now_iso
                if 'progress' in serializable_doc_data and isinstance(serializable_doc_data['progress'], dict):
                    serializable_doc_data['progress']['lastUpdated'] = now_iso

                serializable_doc_data = convert_firestore_timestamps_to_strings(serializable_doc_data)

                payload_dict = {
                    "doc_id": original_doc_id,
                    "file_url": file_url, # Use the public https URL
                    "doc_data": serializable_doc_data, # Pass the corrected, full doc_data
                    "is_sub_document": False,
                    "original_doc_id": original_doc_id,
                    "target_index": target_index,
                    "start_page_original": 1,
                }
                # --- END PAYLOAD FIX ---

                # Create Cloud Task
                task = {
                    'http_request': {
                        'http_method': tasks_v2.HttpMethod.POST,
                        'url': WORKER_URL,
                        'headers': {'Content-type': 'application/json'},
                        'body': json.dumps(payload_dict).encode('utf-8')
                    }
                }

                # Set task deadline (30 minutes)
                deadline = duration_pb2.Duration()
                deadline.seconds = 1800
                task['dispatch_deadline'] = deadline
                
                # Enqueue task
                try:
                    response = tasks_client.create_task(parent=parent, task=task)
                    print(f"[ZIP_IMPORTER] Cloud Task created: {response.name} for doc {original_doc_id}")
                except Exception as task_err:
                    print(f"[ZIP_IMPORTER_ERROR] Failed to create Cloud Task for {filename}: {task_err}")
                    traceback.print_exc()
                    # Mark document as failed if task creation fails
                    batch.update(doc_ref, {
                        'status': 'failed',
                        'lastError': f"Failed to enqueue processing task: {str(task_err)}",
                        'failedAt': SERVER_TIMESTAMP
                    })

                files_processed_count += 1
                print(f"[ZIP_IMPORTER_DEBUG] --- 6. ADDED task for {doc_data.get('title')} ({doc_data.get('fileType')}) with doc_id {original_doc_id}. ---")

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid zip archive.")
    except Exception as e:
        print(f"[ZIP_UPLOAD_ERROR] Job {job_id}: Failed during zip processing. Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process zip file: {str(e)}")
    
    finally:
        # CRITICAL: Clean up the temporary file from the local disk
        if zip_path and os.path.exists(zip_path):
            os.remove(zip_path)
            print(f"[ZIP_IMPORTER_DEBUG] --- 7. Cleaned up temporary zip file: {zip_path} ---")

    # Commit the batch
    batch.commit()
    print(f"[ZIP_IMPORTER_DEBUG] --- 8. Committed {len(created_documents)} documents to Firestore ---\n")


    return ZipUploadResponse(
        message=f"Successfully queued {len(created_documents)} files for processing.",
        job_id=job_id,
        documents=created_documents
    )
