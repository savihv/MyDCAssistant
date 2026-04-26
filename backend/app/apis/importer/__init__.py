# FILE: src/app/apis/importer/__init__.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from app.auth import AuthorizedUser
import csv
import io
import databutton as db
import datetime
import firebase_admin
from firebase_admin import credentials, firestore, auth
import pandas as pd
import json
import asyncio # New import for to_thread
import re
import os
import tempfile
from app.libs.firebase_config import get_firestore_client
from typing import Optional

# --- MODIFIED: Import Pinecone and Gemini client wrapper ---
from pinecone import Pinecone
from pinecone import ServerlessSpec, PineconeException
from app.libs.gemini_client import get_gemini_client


# --- CONSTANTS FOR BATCHING ---
PINECONE_BATCH_SIZE = 100 # Recommended maximum for Pinecone upserts
FIRESTORE_BATCH_SIZE = 200 # A safe, efficient size for Firestore batches

# --- NEW: CONSTANTS FOR PINECONE INDEX CREATION ---
PINECONE_TEXT_DIMENSION = 768
PINECONE_IMAGE_DIMENSION = 1408
PINECONE_METRIC = "cosine"

# --- MODULE LEVEL INITIALIZATION: Executed once at application startup ---
pc: Optional[Pinecone] = None

try:
    # --- 1. Initialize Pinecone client ---
    pinecone_api_key = os.environ.get("PINECONE_API_KEY")
    if not pinecone_api_key:
        raise ValueError("Pinecone API key not found in secrets.")
    pc = Pinecone(api_key=pinecone_api_key)
    print("Importer: Pinecone client configured successfully.")
    
    print("Importer: Using centralized Firebase configuration.")

except Exception as e:
    print(f"Importer: ERROR at startup - Failed to configure services: {e}")
    pc = None
    
# --- FastAPI Router ---
router = APIRouter(
    prefix="/importer",
    tags=["importer"],
)

class CSVUploadResponse(BaseModel):
    success: bool
    records_processed: int
    errors: list[str]
    message: str

class CSVHeadersResponse(BaseModel):
    headers: list[str]

class DeleteHistoricRecordResponse(BaseModel):
    success: bool
    message: str

class BulkDeleteHistoricRecordsRequest(BaseModel):
    record_ids: list[str]
    target_index: str = "historic"

class BulkDeleteHistoricRecordsResponse(BaseModel):
    success: bool
    deleted_count: int
    failed_count: int
    message: str

# This is an internal helper and doesn't need to be an endpoint.
def get_system_fields():
    SYSTEM_FIELDS = {
        'required': ['record_id', 'issue_description', 'resolution'],
        'optional': ['service_date', 'technician_name', 'equipment_model', 'equipment_manufacturer', 'customer_name', 'customer_location', 'technician_notes']
    }
    return SYSTEM_FIELDS

@router.post("/get-csv-headers", response_model=CSVHeadersResponse)
async def get_csv_headers(file: UploadFile = File(...)):
    """
    Reads the header row of a CSV file and returns the column names.
    This is used to populate the column mapping interface on the frontend.
    """
    if not file.content_type == "text/csv":
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")
    
    try:
        # Read just enough of the file to get the header
        contents = await file.read(1024)  # Read first 1KB, should be enough for headers
        await file.seek(0) # Reset file pointer for subsequent reads if needed elsewhere
        
        # Use pandas to efficiently read just the header
        df_header = pd.read_csv(io.BytesIO(contents), nrows=0)
        
        # Sanitize headers (lowercase, strip whitespace) to match backend logic
        sanitized_headers = [col.strip().lower() for col in df_header.columns]

        return CSVHeadersResponse(headers=sanitized_headers)

    except Exception as e:
        # Log the error for debugging, but return an empty list for a graceful frontend
        print(f"[IMPORTER DEBUG] Error reading CSV headers: {e}")
        return CSVHeadersResponse(headers=[])


@router.post("/upload-historic-records-csv", response_model=CSVUploadResponse)
async def upload_historic_records_csv(
    user: AuthorizedUser,
    file: UploadFile = File(...),
    mapping: str = Form(...),
    target_index: str = Form("historic")
):
    """
    Accepts a CSV, validates it, imports to Firestore, and creates/stores
    embeddings in the correct company-specific Pinecone index.
    """
    # --- Check for module-level initialization failures ---
    if not pc or not get_firestore_client():
        raise HTTPException(status_code=500, detail="Core services (Pinecone or Firebase) are not initialized.")

    print(f"[IMPORTER DEBUG] Initiating CSV upload for user ID: {user.sub}")
    company_id = None # Initialize to None for the final except block

    if not file.content_type == "text/csv":
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a CSV file.")

    try:
        # --- Parse Mapping ---
        print(f"[IMPORTER DEBUG] Raw mapping string received: {mapping}")
        try:
            column_mapping = json.loads(mapping)
            print(f"[IMPORTER DEBUG] Parsed column mapping: {column_mapping}")
        except json.JSONDecodeError as e:
            print(f"[IMPORTER DEBUG] ERROR: JSON decoding failed for mapping. Error: {e}")
            raise HTTPException(status_code=400, detail="Invalid mapping format.")

        # Get user custom claims to correctly fetch the company_id
        print(f"[IMPORTER DEBUG] Fetching user record from Firebase Auth for user.sub: {user.sub}")
        # auth.get_user is a synchronous call, run it in a thread
        user_record = await asyncio.to_thread(auth.get_user, user.sub) 
        user_claims = user_record.custom_claims or {}
        print(f"[IMPORTER DEBUG] Retrieved user claims: {user_claims}")
        company_id = user_claims.get('company')
        print(f"[IMPORTER DEBUG] Company ID from claims: {company_id}")

        if not company_id:
            print("[IMPORTER DEBUG] ERROR: Company ID is missing from user claims.")
            raise HTTPException(status_code=403, detail="User is not associated with a company or company claim is missing.")

        # --- MODIFIED: Connect to OR CREATE the Pinecone indexes ---
        sanitized_company_id = company_id.lower().replace('_', '-')

        target_index_name = target_index or "general"
        sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index_name).lower()
        
        # --- Pinecone Setup for TWO Indexes ---
        text_index_name = f"techtalk-text-{sanitized_company_id}"
        image_index_name = f"techtalk-image-{sanitized_company_id}" # New index for images
        namespace = f"{sanitized_company_id}-{sanitized_target_index}"
        
        print(f"[IMPORTER DEBUG] Using global indexes: {text_index_name}, {image_index_name}")
        print(f"[IMPORTER DEBUG] With namespace: {namespace}")     
        
        existing_indexes = await asyncio.to_thread(pc.list_indexes)
        existing_index_names = [index.name for index in existing_indexes]

        # Create TEXT index if it doesn't exist
        if text_index_name not in existing_index_names:
            print(f"[IMPORTER DEBUG] Text index '{text_index_name}' not found. Creating it now...")
            try:
                await asyncio.to_thread(
                    pc.create_index,
                    name=text_index_name,
                    dimension=PINECONE_TEXT_DIMENSION,
                    metric=PINECONE_METRIC,
                    spec=ServerlessSpec(cloud="aws", region="us-east-1")
                )
                print(f"[IMPORTER DEBUG] Successfully created text index '{text_index_name}'.")
            except PineconeException as e:
                if "already exists" in str(e):
                    print(f"[IMPORTER DEBUG] Text index '{text_index_name}' was created by another process. Continuing.")
                else:
                    raise e # Re-raise other creation errors

        # Create IMAGE index if it doesn't exist (using dotproduct metric for consistency)
        if image_index_name not in existing_index_names:
            print(f"[IMPORTER DEBUG] Image index '{image_index_name}' not found. Creating it now...")
            try:
                await asyncio.to_thread(
                    pc.create_index,
                    name=image_index_name,
                    dimension=PINECONE_IMAGE_DIMENSION,
                    metric="dotproduct",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1")
                )
                print(f"[IMPORTER DEBUG] Successfully created image index '{image_index_name}'.")
            except PineconeException as e:
                if "already exists" in str(e):
                    print(f"[IMPORTER DEBUG] Image index '{image_index_name}' was created by another process. Continuing.")
                else:
                    raise e
                    
        # Now, connect to the text index, which is guaranteed to exist.
        pinecone_text_index = pc.Index(text_index_name)
        print(f"[IMPORTER DEBUG] Successfully connected to Pinecone index: {text_index_name}")

        # --- Define System Fields (for reference) ---
        SYSTEM_FIELDS = get_system_fields()

        # --- Read and Sanitize CSV Content ---
        contents = await file.read()
        try:
            # pd.read_csv is synchronous
            df = await asyncio.to_thread(pd.read_csv, io.BytesIO(contents), keep_default_na=False, dtype=str)
            df.columns = [col.strip().lower() for col in df.columns]
            print(f"[IMPORTER DEBUG] CSV parsed into DataFrame. Shape: {df.shape}. Columns: {df.columns.tolist()}")
        except Exception as e:
            print(f"[IMPORTER DEBUG] ERROR: Failed to parse CSV into DataFrame. Error: {e}")
            raise HTTPException(status_code=400, detail=f"Error parsing CSV file: {e}")

        # --- Import to Firestore and Pinecone ---
        collection_path = f"companies/{company_id}/{target_index}_records"
        records_ref = get_firestore_client().collection(collection_path)
        print(f"[IMPORTER DEBUG] Target Firestore collection path: {collection_path}")
        
        batch = get_firestore_client().batch()
        pinecone_vectors_to_upsert = []
        records_processed = 0
        error_list = []

        for index, row in df.iterrows():
            record_to_save = {}
            has_error = False

            for system_field, csv_header in column_mapping.items():
                if not csv_header:  
                    if system_field in SYSTEM_FIELDS['optional']:
                        record_to_save[system_field] = ""
                    continue
                
                value = row.get(csv_header, "").strip()

                if system_field in SYSTEM_FIELDS['required'] and not value:
                    error_list.append(f"Row {index + 2}: Missing required value for mapped column '{csv_header}' (for {system_field}). Skipping row.")
                    has_error = True
                    break
                
                if system_field == 'service_date' and value:
                    try:
                        # pd.to_datetime is synchronous
                        date_val = await asyncio.to_thread(pd.to_datetime, value, errors='raise')
                        record_to_save[system_field] = date_val.to_pydatetime()
                    except (ValueError, TypeError):
                        error_list.append(f"Row {index + 2}: Could not parse date '{value}' from column '{csv_header}'. Storing as string.")
                        record_to_save[system_field] = value
                else:
                    record_to_save[system_field] = value
            
            if has_error:
                continue

            if 'record_id' not in record_to_save or not record_to_save['record_id']:
                error_list.append(f"Row {index + 2}: 'record_id' is missing or empty after mapping. Skipping row.")
                continue

            if index < 3: # Log the first 3 records to be saved
                print(f"[IMPORTER DEBUG] Row {index + 2}: Preparing to save record: {record_to_save}")

            record_to_save['target_index'] = target_index 
            
            # Sanitize doc_id to be Firestore-safe (remove spaces, parentheses, slashes, etc.)
            raw_record_id = record_to_save['record_id']
            doc_id = re.sub(r'[^a-zA-Z0-9_-]', '_', raw_record_id)
            
            # Ensure the original record_id is preserved in the document for reference
            record_to_save['original_record_id'] = raw_record_id
            
            doc_ref = records_ref.document(doc_id)
            
            batch.set(doc_ref, record_to_save)

            # 1. Construct text chunk
            text_to_embed = (
                f"Issue: {record_to_save.get('issue_description', '')}. "
                f"Resolution: {record_to_save.get('resolution', '')}. "
                f"Technician: {record_to_save.get('technician_name', 'N/A')}. "
                f"Notes: {record_to_save.get('technician_notes', '')}"
            )
            
            # 2. Create embedding using Gemini client (AWAIT ASYNCIO.TO_THREAD)
            embedding = await asyncio.to_thread(
                get_gemini_client().embed_text,
                text=text_to_embed,
                model="text-embedding-004",
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=768
            )
            
            # 3. Prepare the vector for Pinecone
            pinecone_vectors_to_upsert.append({
                "id": doc_id,
                "values": embedding,
                "metadata": {
                    "companyId": company_id,
                    "documentId": doc_id,
                    "type": "historic_record",
                    "fileName": f"record_{doc_id}.csv",
                    "target_index": target_index,
                    "original_text": text_to_embed  # ✅ Added original_text for retrieval
                }
            })
            
            records_processed += 1
            
            # --- CORRECTED BATCH COMMIT LOGIC (Independent checks for 100/200) ---
            
            # 4. Commit Pinecone Batch if size reached
            if (len(pinecone_vectors_to_upsert) == PINECONE_BATCH_SIZE):
                print(f"[IMPORTER DEBUG] Committing Pinecone batch of {PINECONE_BATCH_SIZE}. Total processed: {records_processed}")
                # pinecone_text_index.upsert is synchronous
                await asyncio.to_thread(
                    pinecone_text_index.upsert, 
                    vectors=pinecone_vectors_to_upsert, 
                    namespace=namespace
                )
                pinecone_vectors_to_upsert = [] # Reset Pinecone batch

            # 5. Commit Firestore Batch if size reached
            if (records_processed % FIRESTORE_BATCH_SIZE == 0):
                print(f"[IMPORTER DEBUG] Committing Firestore batch of {FIRESTORE_BATCH_SIZE}. Total: {records_processed}")
                # batch.commit() is synchronous
                await asyncio.to_thread(batch.commit)
                batch = get_firestore_client().batch() # Reset Firestore batch

        # --- Commit final remaining items ---
        
        # 6. Commit final remaining Pinecone batch (if any)
        if pinecone_vectors_to_upsert:
            print(f"[IMPORTER DEBUG] Committing final Pinecone batch of {len(pinecone_vectors_to_upsert)} records.")
            await asyncio.to_thread(
                pinecone_text_index.upsert, 
                vectors=pinecone_vectors_to_upsert, 
                namespace=namespace
            )
        
        # 7. Commit final remaining Firestore batch (if not already committed on a round number)
        # We check if the last commit was not exactly at the batch size
        if records_processed % FIRESTORE_BATCH_SIZE != 0: 
            print("[IMPORTER DEBUG] Committing final Firestore batch.")
            await asyncio.to_thread(batch.commit)
        
        final_message = f"Successfully imported and embedded {records_processed} records."
        if error_list:
            final_message += " Some rows were skipped or had issues."
        
        response = CSVUploadResponse(
            success=True,
            records_processed=records_processed,
            errors=error_list,
            message=final_message,
        )
        print(f"[IMPORTER DEBUG] Process finished. Returning response: {response.model_dump_json(indent=2)}")
        return response

    except Exception as e:
        # This will now safely print the company_id if it was retrieved, or None if the error happened before that.
        print(f"[IMPORTER DEBUG] FATAL ERROR in upload_historic_records_csv for company '{company_id}'. Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


def get_user_data(user_id: str):
    """Get user data from Firestore"""
    try:
        user_ref = get_firestore_client().collection('users').document(user_id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        return user_doc.to_dict()
    except Exception as e:
        print(f"Error getting user data: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get user data: {str(e)}")


@router.delete("/historic-records/{record_id}", response_model=DeleteHistoricRecordResponse)
async def delete_historic_record(
    record_id: str,
    user: AuthorizedUser,
    target_index: str = "historic"
):
    """
    Deletes a single historic record from Firestore and Pinecone.
    """
    if not pc or not get_firestore_client():
        raise HTTPException(status_code=500, detail="Core services not initialized")
    
    try:
        # Get user data and company
        print(f"[DELETE DEBUG] Fetching user record for user.sub: {user.sub}")
        user_record = await asyncio.to_thread(auth.get_user, user.sub)
        user_claims = user_record.custom_claims or {}
        company_id = user_claims.get('company')
        
        if not company_id:
            raise HTTPException(status_code=400, detail="User not associated with a company")

        # Delete from Firestore
        collection_path = f"companies/{company_id}/{target_index}_records"
        records_ref = get_firestore_client().collection(collection_path)
        doc_ref = records_ref.document(record_id)
        
        doc_snapshot = await asyncio.to_thread(doc_ref.get)
        if not doc_snapshot.exists:
            raise HTTPException(status_code=404, detail="Record not found")
        
        await asyncio.to_thread(doc_ref.delete)
        print(f"✅ Deleted Firestore record: {record_id}")

        # Delete from Pinecone
        pinecone_api_key = os.environ.get("PINECONE_API_KEY")
        if pinecone_api_key:
            sanitized_company_id = company_id.lower().replace('_', '-')
            sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index or 'historic').lower()
            text_index_name = f"techtalk-text-{sanitized_company_id}"
            namespace = f"{sanitized_company_id}-{sanitized_target_index}"
            
            try:
                index = pc.Index(text_index_name)
                
                # Delete the specific vector by ID
                await asyncio.to_thread(
                    index.delete,
                    ids=[record_id],
                    namespace=namespace
                )
                print(f"✅ Deleted Pinecone vector for record: {record_id}")
            except Exception as e:
                print(f"⚠️ Failed to delete from Pinecone: {e}")
        
        return DeleteHistoricRecordResponse(
            success=True,
            message=f"Record {record_id} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting historic record: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete record: {str(e)}")


@router.post("/bulk-delete-historic-records", response_model=BulkDeleteHistoricRecordsResponse)
async def bulk_delete_historic_records(
    request: BulkDeleteHistoricRecordsRequest,
    user: AuthorizedUser
):
    """
    Deletes multiple historic records from Firestore and Pinecone.
    """
    firestore_db = get_firestore_client()
    if not pc or not firestore_db:
        raise HTTPException(status_code=500, detail="Core services not initialized")
    
    if not request.record_ids:
        raise HTTPException(status_code=400, detail="No record IDs provided")
    
    try:
        # Get user data and company
        print(f"[BULK DELETE DEBUG] Processing bulk delete for {len(request.record_ids)} records")
        user_record = await asyncio.to_thread(auth.get_user, user.sub)
        user_claims = user_record.custom_claims or {}
        company_id = user_claims.get('company')
        
        if not company_id:
            raise HTTPException(status_code=400, detail="User not associated with a company")

        collection_path = f"companies/{company_id}/{request.target_index}_records"
        records_ref = get_firestore_client().collection(collection_path)
        
        deleted_count = 0
        failed_count = 0


        # Delete from Firestore in batches
        batch = firestore_db.batch()
        batch_count = 0
        
        for record_id in request.record_ids:
            try:
                doc_ref = records_ref.document(record_id)
                batch.delete(doc_ref)
                batch_count += 1
                
                # Firestore batches have a 500 operation limit
                if batch_count >= 500:
                    await asyncio.to_thread(batch.commit)
                    batch = firestore_db.batch()
                    batch_count = 0
                    
                deleted_count += 1
            except Exception as e:
                print(f"Failed to batch delete record {record_id}: {e}")
                failed_count += 1
        
        # Commit remaining batch
        if batch_count > 0:
            await asyncio.to_thread(batch.commit)
        
        print(f"✅ Deleted {deleted_count} Firestore records")

        # Delete from Pinecone
        pinecone_api_key = os.environ.get("PINECONE_API_KEY")
        if pinecone_api_key:
            sanitized_company_id = company_id.lower().replace('_', '-')
            sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', request.target_index).lower()
            text_index_name = f"techtalk-text-{sanitized_company_id}"
            namespace = f"{sanitized_company_id}-{sanitized_target_index}"
            
            try:
                index = pc.Index(text_index_name)
                
                # Delete all vectors by their IDs
                await asyncio.to_thread(
                    index.delete,
                    ids=request.record_ids,
                    namespace=namespace
                )
                
                print(f"✅ Deleted Pinecone vectors for {len(request.record_ids)} records")
            except Exception as e:
                print(f"⚠️ Failed to delete from Pinecone: {e}")
        
        return BulkDeleteHistoricRecordsResponse(
            success=True,
            deleted_count=deleted_count,
            failed_count=failed_count,
            message=f"Successfully deleted {deleted_count} record(s). {failed_count} failed."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in bulk delete: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Bulk delete failed: {str(e)}")


@router.get("/historic-records")
async def list_historic_records(
    user: AuthorizedUser,
    target_index: str = "historic",
    limit: int = 50,
    offset: int = 0
):
    """
    Lists historic records for the user's company.
    """
    # Use centralized Firestore client
    firestore_db = get_firestore_client()
    if not firestore_db:
        raise HTTPException(status_code=500, detail="Firestore not initialized")
    
    try:
        # Get user data and company
        user_record = await asyncio.to_thread(auth.get_user, user.sub)
        user_claims = user_record.custom_claims or {}
        company_id = user_claims.get('company')
        
        if not company_id:
            raise HTTPException(status_code=400, detail="User not associated with a company")

        collection_path = f"companies/{company_id}/{target_index}_records"
        records_ref = firestore_db.collection(collection_path)
        
        # Query records with pagination - order by record_id since imported_at may not exist
        query = records_ref.order_by('record_id').limit(limit).offset(offset)
        docs = await asyncio.to_thread(lambda: list(query.stream()))
        
        records = []
        for doc in docs:
            record_data = doc.to_dict()
            record_data['id'] = doc.id
            records.append(record_data)
        
        # Get total count
        all_docs = await asyncio.to_thread(lambda: list(records_ref.stream()))
        total_count = len(all_docs)
        
        return {
            "records": records,
            "total": total_count,
            "has_more": (offset + limit) < total_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error listing historic records: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to list records: {str(e)}")
