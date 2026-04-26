from fastapi import APIRouter, Body, HTTPException, Depends, Header, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Union
import databutton as db
import tempfile
import os
import json
import traceback
import asyncio
import imghdr
import time
import math # For ceil in splitting
import gc # For garbage collection
import datetime 
import re

from google.cloud.firestore import Client as FirestoreClient, SERVER_TIMESTAMP, Increment  # type: ignore
from google.cloud import tasks_v2  # type: ignore
from google.cloud import storage as gcs  # type: ignore
from google.oauth2 import service_account  # type: ignore


import pinecone  # type: ignore
from pinecone import Pinecone, ServerlessSpec  # type: ignore
import fitz  # type: ignore # PyMuPDF
from PIL import Image  # type: ignore
import io
import threading
from app.libs.auth_helpers import verify_internal_worker_request
from striprtf.striprtf import rtf_to_text  # type: ignore
from langchain_text_splitters import RecursiveCharacterTextSplitter  # type: ignore

from google.cloud.firestore import DocumentReference  # type: ignore

from app.libs.firebase_config import get_firestore_client, get_firebase_credentials_dict, get_gcs_credentials, get_gcs_project_id
from app.libs.gemini_client import get_gemini_client


router = APIRouter()

# --- Constants ---
DEFAULT_GCS_BUCKET_NAME = "techtalk-document-images" # Used for storing uploaded processed images
DOCUMENTS_GCS_BUCKET_NAME = "techtalk-documents" # Used for original PDFs and temporary sub-PDFs

# PDF Splitting Configuration
PDF_SPLIT_THRESHOLD = 40 # Pages above which a PDF will be split
PAGES_PER_SUB_PDF = 30 # Number of pages in each generated sub-PDF
GCS_SUB_DOCS_FOLDER = "sub_documents" # New GCS folder for temporary sub-PDFs

# Pinecone Batching Configuration
PINECONE_BATCH_SIZE = 60 # Number of vectors to accumulate before sending to Pinecone in one batch

# Retry Configuration for Cloud Tasks
MAX_RETRIES = 6 # Maximum number of retries before marking a task as permanently_failed


# --- RTF Conversion Utility ---

def read_and_clean_rtf(file_path: str) -> str:
    """
    Reads an RTF file, converts its content to plain text using striprtf,
    and returns the cleaned text.

    Args:
        file_path: The local path to the RTF document.

    Returns:
        The extracted plain text content, or an empty string if an error occurs.
    """
    try:
        # 1. Read the raw RTF content from the file
        with open(file_path, 'r', encoding='utf-8') as f:
            rtf_content = f.read()

        # 2. Convert RTF to plain text
        # The striprtf library handles the parsing and removal of formatting codes.
        plain_text = rtf_to_text(rtf_content)

        print(f"✅ Successfully converted RTF file at {file_path} to plain text.")
        return plain_text.strip()
    
    except FileNotFoundError:
        print(f"🚨 Error: File not found at {file_path}")
        return ""
    except Exception as e:
        # Catches potential errors during file reading or RTF parsing
        print(f"🚨 Error processing RTF file {file_path}: {e}")
        return ""

def read_plain_text_file(file_path: str) -> str:
    """
    Reads a plain text file (e.g., .py, .tf, .c, .cpp, .json, .yaml)
    and returns its content as a string.
    
    Args:
        file_path: The local path to the text file.
    
    Returns:
        The file content as plain text, or an empty string if an error occurs.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"✅ Successfully read text file at {file_path}")
        return content.strip()
    except FileNotFoundError:
        print(f"🚨 Error: File not found at {file_path}")
        return ""
    except UnicodeDecodeError:
        # Try with different encoding if UTF-8 fails
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
            print(f"✅ Successfully read text file at {file_path} with latin-1 encoding")
            return content.strip()
        except Exception as e:
            print(f"🚨 Error reading file {file_path}: {e}")
            return ""
    except Exception as e:
        print(f"🚨 Error processing text file {file_path}: {e}")
        return ""
        
# --- Text Chunking Utility ---

def chunk_text_by_token(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """
    Splits a long string of text into smaller, overlapping chunks suitable for
    vectorization and retrieval, using LangChain's RecursiveCharacterTextSplitter.

    This splitter attempts to split the text based on a hierarchy of delimiters
    (like newlines, double newlines, spaces, etc.) to keep meaningful passages together.

    Args:
        text: The large block of clean text to be segmented.
        chunk_size: The maximum size of each text chunk (in characters/tokens).
        chunk_overlap: The overlap between consecutive chunks.

    Returns:
        A list of text strings (the chunks).
    """
    if not text.strip():
        print("⚠️ Warning: Empty text provided for chunking. Returning empty list.")
        return []

    # Initialize the RecursiveCharacterTextSplitter.
    # We use common separators to ensure the splits happen logically (e.g., between paragraphs).
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # Default separators prioritize preserving semantic structure:
        # Paragraphs -> Sentences -> Words
        separators=[
            "\n\n", # Double newline (paragraph break)
            "\n",   # Single newline
            " ",    # Space
            "",     # Fallback for splitting long strings without spaces
        ],
        length_function=len, # Use character count as length metric
        is_separator_regex=False
    )

    # Split the document into chunks
    chunks = text_splitter.split_text(text)
    print(f"✅ Text split into {len(chunks)} chunks (Size: {chunk_size}, Overlap: {chunk_overlap}).")
    return chunks

def run_process_document_worker_task(payload_dict: dict):
    """
    A simple synchronous wrapper to trigger the async worker.
    This is designed to be called safely by BackgroundTasks from other modules.
    """
    print("[DOC_PROCESSOR_DEBUG] --- 1. Entered run_process_document_worker_task ---")
    try:
        doc_id_for_log = payload_dict.get('doc_id', 'UNKNOWN_DOC_ID')
        print(f"[DOC_PROCESSOR_DEBUG] --- 2. Preparing to create Pydantic model for doc_id: {doc_id_for_log} ---")
        
        # Create the Pydantic model from the dictionary
        payload = WorkerPayload(**payload_dict)
        print(f"[DOC_PROCESSOR_DEBUG] --- 3. Pydantic model CREATED successfully for doc_id: {doc_id_for_log} ---")
        
        # Run the main async worker function in a new asyncio event loop
        print(f"[DOC_PROCESSOR_DEBUG] --- 4. Preparing to call asyncio.run() for doc_id: {doc_id_for_log} ---")
        asyncio.run(process_document_worker(payload=payload))
        print(f"[DOC_PROCESSOR_DEBUG] --- 5. asyncio.run() COMPLETED for doc_id: {doc_id_for_log} ---")
        
        print(f"[WORKER_TASK_RUNNER] Successfully completed task for doc_id: {payload.doc_id}")
    except Exception as e:
        doc_id_for_log = payload_dict.get('doc_id', 'UNKNOWN_DOC_ID_IN_ERROR')
        print(f"--- [CRITICAL_ERROR] --- [DOC_PROCESSOR_DEBUG] --- X. EXCEPTION CAUGHT in wrapper for doc_id: {doc_id_for_log} ---")
        print(f"--- [CRITICAL_ERROR] --- [DOC_PROCESSOR_DEBUG] --- Error Details: {e} ---")
        traceback.print_exc()


# --- Pydantic Models ---
class WorkerPayload(BaseModel):
    doc_id: str # This will be original_doc_id OR sub_doc_id
    file_url: str # GCS URL of the PDF to be processed by this specific task
    doc_data: Dict[str, Any] # All metadata is now nested here
    is_sub_document: bool
    original_doc_id: str # This is crucial for linking sub-documents back to their parent
    target_index: Optional[str] = "general"
    start_page_original: int # This indicates the starting page for this chunk in the original document

# 1. ADD THE AUTHENTICATION FUNCTION
async def verify_internal_auth(authorization: str = Header(...)):
    """Validates a secret bearer token for internal service-to-service calls."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    
    token = authorization.split(" ")[1]
    expected_token = os.environ.get("INTERNAL_WORKER_AUTH_KEY")
    
    if not expected_token:
        print("CRITICAL: INTERNAL_WORKER_AUTH_KEY secret is not set.")
        raise HTTPException(status_code=500, detail="Internal server configuration error.")
    
    if token != expected_token:
        raise HTTPException(status_code=403, detail="Invalid internal auth key")
    
    return True

# --- Embedding and Pinecone Setup ---
# --- GLOBAL CACHE AND LOCK FOR EMBEDDING ADAPTER ---
_embedding_adapter_cache: Optional["MultimodalEmbeddingAdapter"] = None
_embedding_adapter_lock = threading.Lock()
# --- END GLOBAL CACHE AND LOCK ---

# You might want to add caching like get_embeddings_model for efficiency
_pinecone_client_cache: Optional[pinecone.Pinecone] = None
_pinecone_client_lock = threading.Lock() # Ensure threading is imported

def get_pinecone_client(api_key: str) -> pinecone.Pinecone:
    global _pinecone_client_cache
    if _pinecone_client_cache:
        return _pinecone_client_cache

    with _pinecone_client_lock:
        if _pinecone_client_cache:
            return _pinecone_client_cache
        print("--- GLOBAL CACHE: Initializing Pinecone client for the first time... ---")
        try:
            client = pinecone.Pinecone(api_key=api_key)
           
            _pinecone_client_cache = client
            print("--- GLOBAL CACHE: Pinecone client initialized and cached.---")
            return client
        except Exception as e:
            print(f" Failed to initialize and cache Pinecone client: {e}")
            raise HTTPException(status_code=500, detail=f"Pinecone client initialization error: {e}")
            
class MultimodalEmbeddingAdapter:
    """Adapter for multimodal embeddings using GeminiClient.
    
    Maintains the same interface as the old Vertex AI implementation
    but uses the centralized GeminiClient internally.
    """
    def __init__(self, project_id: str, location: str, credentials):
        """Initialize the adapter with GeminiClient.
        
        Note: project_id, location, and credentials parameters are kept for
        backward compatibility but are not used since GeminiClient gets
        credentials from secrets.
        """
        try:
            from app.libs.gemini_client import get_gemini_client
            self.gemini_client = get_gemini_client()
            print("[MultimodalEmbeddingAdapter] ✅ Initialized with GeminiClient")
        except Exception as e:
            print(f"[MultimodalEmbeddingAdapter] ❌ Failed to initialize: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to initialize embedding models: {e}") from e

    def embed_text(self, texts: List[str]) -> List[List[float]]:
        """Embeds text using the text-embedding-004 model (768 dimensions)."""
        if not texts:
            return []
        try:
            # Use GeminiClient's batch embed method
            embeddings = self.gemini_client.batch_embed(
                texts=texts,
                model="text-embedding-004",
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=768
            )
            return embeddings
        except Exception as e:
            print(f"[MultimodalEmbeddingAdapter] Error embedding text batch: {e}")
            # Return list of empty lists for consistency with old implementation
            return [[] for _ in texts]

    def embed_image(self, image_bytes: bytes) -> List[float]:
        """Embeds an image using the multimodalembedding@001 model (1408 dimensions)."""
        try:
            embedding = self.gemini_client.embed_image(
                image_bytes=image_bytes,
                mime_type="image/jpeg",
                model="multimodalembedding@001",
                output_dimensionality=1408
            )
            return embedding
        except Exception as e:
            print(f"[MultimodalEmbeddingAdapter] Error generating image embedding: {e}")
            raise  # Re-raise to propagate the error

    def embed_query_for_image_search(self, query: str) -> List[float]:
        """
        Embeds a text query specifically for searching in an image vector space.
        This generates an image-compatible embedding from the text query.
        """
        if not query or not query.strip():
            print("[MultimodalEmbeddingAdapter] Warning: embed_query_for_image_search received an empty query.")
            raise ValueError("Query cannot be empty.")

        try:
            # Use GeminiClient's text-for-image-search method
            embedding = self.gemini_client.embed_text_for_image_search(
                text=query,
                model="multimodalembedding@001",
                output_dimensionality=1408
            )
            
            # Check if the model returned a valid embedding
            if not embedding:
                raise ValueError("Model returned an empty embedding for the query. This may be due to safety filters or an invalid query.")
            
            return embedding
            
        except Exception as e:
            print(f"[MultimodalEmbeddingAdapter] Error generating image-search embedding from text query: {e}")
            raise

def get_embeddings_model():
    """
    Initializes and returns the MultimodalEmbeddingAdapter using a global cache
    to ensure it's loaded only once across all worker instances.
"""
    global _embedding_adapter_cache

    # First, check if the adapter is already cached (avoids locking every time)
    if _embedding_adapter_cache:
        return _embedding_adapter_cache

    # If not cached, acquire a lock to ensure only one thread initializes it
    with _embedding_adapter_lock:
        # Double-check if another thread initialized it while we waited for the lock
        if _embedding_adapter_cache:
            return _embedding_adapter_cache

 
        # If still not cached, this thread will create the adapter
        try:
            print("--- GLOBAL CACHE: Initializing MultimodalEmbeddingAdapter for the first time... ---")
            credentials = get_gcs_credentials()
            project_id = get_gcs_project_id()


            # Create the one-and-only instance
            adapter = MultimodalEmbeddingAdapter(project_id=project_id, location="us-central1", credentials=credentials)
            # Store it in the global cache
            _embedding_adapter_cache = adapter
            
            print("--- GLOBAL CACHE: MultimodalEmbeddingAdapter initialized and cached.---")
            return _embedding_adapter_cache
        except Exception as e:
            # FIX: Changed error handling to be more robust.
            # Raising a standard error instead of HTTPException makes this function
            # more reusable and prevents silent crashes in the main app.
            error_message = f"Failed to initialize and cache MultimodalEmbeddingAdapter: {e}"
            print(f"--- [doc_processor_ERROR] {error_message} ---")
            traceback.print_exc()
            raise ValueError(error_message) from e

# IMPORTANT: This function is NO LONGER USED for Pinecone indexing.
# It's kept here if you still want to generate descriptions for other purposes (e.g., UI display).
# If you don't need it, you can remove it entirely.
async def describe_image_with_gemini_pro_vision(image_bytes: bytes, gemini_api_key: str) -> str:
    try:
        from app.libs.gemini_client import get_gemini_client
        gemini = get_gemini_client()
        
        # Use GeminiClient's generate_with_image method
        response = await asyncio.to_thread(
            gemini.generate_with_image,
            prompt="Describe this image in detail. Focus on key objects, text, and overall context.",
            image_bytes=image_bytes,
            model="gemini-2.0-flash-exp"
        )
        return response
    except Exception as e:
        print(f"[doc_processor] Error describing image with Gemini: {e}")
        return "Could not generate description for image."


async def upload_image_to_gcs(image_bytes: bytes, destination_blob_name: str) -> str:
    try:
 
        credentials = get_gcs_credentials()
        client = await asyncio.to_thread(gcs.Client, credentials=credentials)
        bucket = await asyncio.to_thread(client.bucket, DEFAULT_GCS_BUCKET_NAME)

        # Check and create bucket in a blocking fashion within to_thread
        if not await asyncio.to_thread(bucket.exists):
            print(f"GCS bucket {DEFAULT_GCS_BUCKET_NAME} does not exist. Attempting to create.")
            await asyncio.to_thread(client.create_bucket, bucket, location="US")
            
 
        blob = await asyncio.to_thread(bucket.blob, destination_blob_name)
        image_type = imghdr.what(None, h=image_bytes) or 'png'
        content_type = f"image/{image_type}"
        await asyncio.to_thread(blob.upload_from_string, image_bytes, content_type=content_type)
        return blob.public_url
    except Exception as e:
        print(f" Error during GCS upload for '{destination_blob_name}': {e}")
        raise

async def _process_content_from_page(
    original_doc_id: str,
    true_original_page_number: int,
    
pdf_doc_current_chunk: fitz.Document,
    page_number_in_current_chunk: int,
    # gemini_api_key: str, # No longer needed here for Pinecone indexing
    company_id: str
):
    """
    Extracts text and images from a given page of a PDF document chunk.
Images are extracted as raw bytes for direct embedding.
    Args:
        original_doc_id (str): The ID of the original main document.
true_original_page_number (int): The 1-indexed actual page number in the original full document.
pdf_doc_current_chunk (fitz.Document): The PyMuPDF document object of the current sub-PDF/chunk.
page_number_in_current_chunk (int): The 1-indexed page number of *this specific page* within `pdf_doc_current_chunk`.
# gemini_api_key (str): API key for Gemini (removed for direct image embedding).
        credentials_path (str): Path to GCP service account credentials.
company_id (str): Company ID for GCS bucket structure.
    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each representing an extracted text or image element.
Image elements now include 'image_bytes' instead of 'content' description.
    """
    page_elements = []
    # Load the correct page from the current chunk
    page = await asyncio.to_thread(pdf_doc_current_chunk.load_page, page_number_in_current_chunk - 1)

    text = await asyncio.to_thread(page.get_text, "text")
    if text and text.strip():
        page_elements.append({"type": "text", "content": text, "metadata": {"page_number": true_original_page_number}})
        
    image_list = await asyncio.to_thread(page.get_images, full=True)
    for img_index, img_info in enumerate(image_list):
        xref = img_info[0]
        base_image = await asyncio.to_thread(pdf_doc_current_chunk.extract_image, xref)
        image_bytes = base_image["image"]
        
        # --- Image Downsampling for reduced burden (still useful for GCS storage) ---
        processed_image_bytes = image_bytes
        try:
            pil_img = await asyncio.to_thread(Image.open, io.BytesIO(image_bytes))
            # Resize if larger than a certain dimension (e.g., max 1024 on longest side)
            if max(pil_img.size) > 1024:
                print(f"Downsampling image from {pil_img.size}...")
                with io.BytesIO() as output:
                    await asyncio.to_thread(pil_img.thumbnail, (1024, 1024), Image.Resampling.LANCZOS)
              
                    await asyncio.to_thread(pil_img.save, output, format="PNG")
                    processed_image_bytes = output.getvalue()
                print(f"Image downsampled to {pil_img.size}")

        except Exception as e:
            print(f"Warning: Failed to downsample image {img_index} on page {true_original_page_number}, using original. Error: {e}")
        # --- End Image Downsampling ---
        
        # NOTE: describe_image_with_gemini_pro_vision is NO LONGER CALLED HERE FOR INDEXING
        # You could call it here for other purposes (e.g., storing a description in metadata for display)
        # but for direct image embedding, it's not needed for the vector.
        # description = await describe_image_with_gemini_pro_vision(processed_image_bytes, gemini_api_key) # REMOVED

   
        # Use the true_original_page_number for GCS path to group images by original document pages
        # Validate IDs don't contain path traversal (defense in depth)
        if '..' in company_id or '..' in original_doc_id:
            raise ValueError("Invalid path in company_id or document_id")
        
        # Use the true_original_page_number for GCS path to group images by original document pages
        gcs_image_name = f"companies/{company_id}/documents/{original_doc_id}/images/page_{true_original_page_number}_img_{img_index}.png"
        gcs_url = await upload_image_to_gcs(processed_image_bytes, gcs_image_name)
        
        page_elements.append({
            "type": "image",
            "image_bytes": processed_image_bytes, # Store the actual bytes for embedding
          
            "metadata": {
                "page_number": true_original_page_number,
                "gcs_url": gcs_url,
                # Optionally, you could store a brief description here if needed for UI,
                # but it won't be embedded for vector search.
                # "gemini_description": description # If you still call describe_image...
            }
        })
    return page_elements


async def vectorize_and_store_elements(doc_id: str, elements: List[Dict[str, Any]], doc_data: dict, embeddings_model: MultimodalEmbeddingAdapter) -> Dict[str, List[Dict[str, Any]]]:
    """
    Vectorizes a list of page elements and RETURNS them as Pinecone-ready dictionaries, separated by type.
    Args:
        doc_id (str): The ORIGINAL_DOC_ID for grouping in Pinecone.
        elements (List[Dict[str, Any]]): List 
of extracted page elements.
        doc_data (dict): Original document metadata.
        embeddings_model (MultimodalEmbeddingAdapter): Initialized embeddings model.
    Returns:
        Dict[str, List[Dict[str, Any]]]: A dictionary with keys 'text_vectors' and 'image_vectors',
                                         each containing a list of Pinecone-ready vectors.
    """
 
    if not elements: return {"text_vectors": [], "image_vectors": []}

    texts_to_embed = []
    text_elements_map = {} # Map content back to original element for metadata
    
    images_to_embed = []
    image_elements_map = {} # Map content back to original element for metadata

    for i, el in enumerate(elements):
        if el['type'] == 'text':
            texts_to_embed.append(el['content'])
            text_elements_map[len(texts_to_embed) - 1] = i # Map index in texts_to_embed to original elements index
        elif el['type'] == 'image':
            images_to_embed.append(el['image_bytes'])
            image_elements_map[len(images_to_embed) - 1] = i # Map index in images_to_embed to original elements index
    
    text_vectors_for_batch = []
    image_vectors_for_batch = []

    # Embed texts
    if texts_to_embed:
        text_embeddings = embeddings_model.embed_text(texts_to_embed)
   
        for i, embedding in enumerate(text_embeddings):
            if embedding:
                original_element_idx = text_elements_map[i]
                element = elements[original_element_idx]
                chunk_id = f"{doc_id}-p{element['metadata']['page_number']}-text-{original_element_idx}"
                metadata = {
      
                    "document_id": doc_id,
                    "chunk_id": chunk_id,
                    "type": element['type'],
                    "file_name": doc_data.get("fileName"),
                    "company": doc_data.get("company"),
 
                    "original_text": element['content'], # Store original text content
                    **element.get("metadata", {})
                }
                text_vectors_for_batch.append({"id": chunk_id, "values": embedding, "metadata": metadata})

    # Embed images
    if images_to_embed:
      
        for i, img_bytes in enumerate(images_to_embed):
            try:
                embedding = embeddings_model.embed_image(img_bytes) # Direct image embedding (1408-dim)
                if embedding:
                    original_element_idx = image_elements_map[i]
                    element = elements[original_element_idx]
                    chunk_id = f"{doc_id}-p{element['metadata']['page_number']}-image-{original_element_idx}"
                    metadata = {
                        "document_id": doc_id,
                        "chunk_id": chunk_id,
    
                        "type": element['type'],
                        "file_name": doc_data.get("fileName"),
                        "company": doc_data.get("company"),
                        "gcs_url": element['metadata'].get('gcs_url'), # GCS URL to image
                        # No 'original_text' here, as it's an image.
                        # You could add a 'description' field
                        # if you generate one separately for display, but it's not embedded.
                        **element.get("metadata", {})
                    }
                    image_vectors_for_batch.append({"id": chunk_id, "values": embedding, "metadata": metadata})
            except Exception as e:
                print(f" Failed to embed image {i} for doc {doc_id}: {e}")
              
# Log error but continue with other images if possible

    return {"text_vectors": text_vectors_for_batch, "image_vectors": image_vectors_for_batch}


async def upsert_pinecone_batch_text(index: 'pinecone.Index', vectors: List[Dict[str, Any]], namespace: str):
    """Performs a single batch upsert for TEXT vectors to Pinecone."""
    if not vectors:
        return 0
    try:
        await asyncio.to_thread(index.upsert, vectors=vectors, namespace=namespace)
        print(f"Successfully upserted {len(vectors)} TEXT vectors to Pinecone in a batch.")
        return len(vectors)
    
    except pinecone.core.client.ApiException as api_e:
        print(f" Pinecone API Error during TEXT batch upsert: {api_e.body} (Status: {api_e.status})")
        traceback.print_exc()
        raise
    except Exception as e:
        print(f" General Error during Pinecone TEXT batch upsert: {e}")
        traceback.print_exc()
        raise

async def upsert_pinecone_batch_image(index: 'pinecone.Index', vectors: List[Dict[str, Any]], namespace: str):
    """Performs a single batch upsert for IMAGE vectors to Pinecone."""
   
    if not vectors:
        return 0
    try:
        await asyncio.to_thread(index.upsert, vectors=vectors, namespace=namespace)
        print(f"Successfully upserted {len(vectors)} IMAGE vectors to Pinecone in a batch.")
        return len(vectors)
    except pinecone.core.client.ApiException as api_e:
        print(f" Pinecone API Error during IMAGE batch upsert: {api_e.body} (Status: {api_e.status})")
        traceback.print_exc()
        raise
    except Exception as e:
        print(f" General Error during Pinecone IMAGE batch upsert: {e}")
        traceback.print_exc()
        raise


async def task_process_page_rtf(
    original_doc_id: str, # The main document ID (used for Firestore updates & Pinecone document_id)
    page_number_in_sub_pdf: int, # Page number relative to the current sub-PDF (1-indexed)
    total_pages_in_sub_pdf: int, # Total pages in the current sub-PDF (not strictly used here, but for context)
    pdf_doc_sub: str, # The opened rtf
    doc_data: Dict[str, Any], # Original doc_data (passed to keep totalPages consistent)
    embeddings_model: 'MultimodalEmbeddingAdapter',
    # gemini_api_key: str, # No longer directly needed in this function for vectorization
    start_page_original: int # Starting page of this sub-PDF in the original document (1-indexed)
):
    """
    Processes a single page from a PDF chunk (sub-PDF or full PDF).
This task extracts content and vectorizes it, returning the vectors (text and image).
Firestore updates and Pinecone upserts are handled by the orchestrator.
Returns:
        Dict[str, Any]: A dictionary containing 'text_vectors', 'image_vectors', and 'chunks_created' (total count).
"""
    true_original_page_number = -1 # Initialize with invalid value
    page_elements = []
    
    try:
        # Calculate the actual page number in the original document
        true_original_page_number = start_page_original + page_number_in_sub_pdf - 1
  
        # Assuming 'rtf_chunk_content' holds the text content for the current chunk
        # and 'original_doc_id' and 'true_original_page_number' are available from the loop
        rtf_chunk_content = pdf_doc_sub # Rename this variable for clarity (e.g., rtf_chunk_content)

        page_elements.append({"type": "text", "content": rtf_chunk_content, "metadata": {"page_number": true_original_page_number}})
 
        print(f"  [RTF] Prepared structured elements for chunk {true_original_page_number}.")

        # Vectorize elements but do NOT upsert here return them for batching
        # This will now return separate lists for text and image vectors
        vectors_by_type = await vectorize_and_store_elements(
            original_doc_id, # Use original doc_id for Pinecone grouping
            page_elements,
            doc_data, # Pass original doc_data for file_name, company etc.
            embeddings_model
    
        )
        
        return {
            "text_vectors": vectors_by_type["text_vectors"],
            "image_vectors": vectors_by_type["image_vectors"],
            "chunks_created": len(vectors_by_type["text_vectors"]) + len(vectors_by_type["image_vectors"])
        }
        
    except Exception as e:
        error_message = f"Failed on page {true_original_page_number} (from sub-document {page_number_in_sub_pdf}) of original document {original_doc_id}: {str(e)}"
        print(f" {error_message}")
        traceback.print_exc()
        # Re-raise the exception; orchestrator will catch and update Firestore status to 'failed'
        raise e
    finally:
        # Explicitly delete page_elements and collect garbage
        if 'page_elements' in locals():
            del page_elements
        gc.collect()


async def task_process_page(
    original_doc_id: str, # The main document ID (used for Firestore updates & Pinecone document_id)
    page_number_in_sub_pdf: int, # Page number relative to the current sub-PDF (1-indexed)
    total_pages_in_sub_pdf: int, # Total pages in the current sub-PDF (not strictly used here, but for context)
    pdf_doc_sub: fitz.Document, # The opened sub-PDF document object (or full PDF for small docs)
    doc_data: Dict[str, Any], # Original doc_data (passed to keep totalPages consistent)
    embeddings_model: 'MultimodalEmbeddingAdapter',
    # gemini_api_key: str, # No longer directly needed in this function for vectorization
    start_page_original: int # Starting page of this sub-PDF in the original document (1-indexed)
):
    """
    Processes a single page from a PDF chunk (sub-PDF or full PDF).
This task extracts content and vectorizes it, returning the vectors (text and image).
Firestore updates and Pinecone upserts are handled by the orchestrator.
Returns:
        Dict[str, Any]: A dictionary containing 'text_vectors', 'image_vectors', and 'chunks_created' (total count).
"""
    true_original_page_number = -1 # Initialize with invalid value

    try:
        # Calculate the actual page number in the original document
        true_original_page_number = start_page_original + page_number_in_sub_pdf - 1

        if page_number_in_sub_pdf > pdf_doc_sub.page_count:
            print(f"Warning: Attempted to process page {page_number_in_sub_pdf} which is beyond sub-PDF count {pdf_doc_sub.page_count}")
            return {"text_vectors": [], "image_vectors": [], "chunks_created": 0}

  
        # Extract content (images now include raw bytes)
        page_elements = await _process_content_from_page(
            original_doc_id, # For GCS pathing
            true_original_page_number, # For Pinecone metadata
            pdf_doc_sub,
            page_number_in_sub_pdf, # The 1-indexed page within the current chunk
            doc_data['company'] # Company ID from original doc_data
        )
        
        # Vectorize elements but do NOT upsert here return them for batching
        # This will now return separate lists for text and image vectors
        vectors_by_type = await vectorize_and_store_elements(
            original_doc_id, # Use original doc_id for Pinecone grouping
            page_elements,
            doc_data, # Pass original doc_data for file_name, company etc.
            embeddings_model
    
        )
        
        return {
            "text_vectors": vectors_by_type["text_vectors"],
            "image_vectors": vectors_by_type["image_vectors"],
            "chunks_created": len(vectors_by_type["text_vectors"]) + len(vectors_by_type["image_vectors"])
        }
        
    except Exception as e:
        error_message = f"Failed on page {true_original_page_number} (from sub-document {page_number_in_sub_pdf}) of original document {original_doc_id}: {str(e)}"
        print(f" {error_message}")
        traceback.print_exc()
        # Re-raise the exception; orchestrator will catch and update Firestore status to 'failed'
        raise e
    finally:
        # Explicitly delete page_elements and collect garbage
        if 'page_elements' in locals():
            del page_elements
        gc.collect()


async def task_finalize_document(doc_id: str):
    """
    Finalizes the processing status of the main document in Firestore and cleans up temporary sub-PDFs.
    """
  
    db_client = get_firestore_client()
    doc_ref = await asyncio.to_thread(db_client.collection('documents').document, doc_id)
    
    # Update final status and set progress to 100%
    print(f"--- FINALIZER: Attempting to update document {doc_id} to processed status. ---")
    await asyncio.to_thread(doc_ref.update, {
        "status": "processed",
        "isProcessed": True,
        "processedAt": SERVER_TIMESTAMP,
        "progress": {"stage": "complete", "progress": 100, "message": "Document processed successfully."}
    })
   
    print(f"--- FINALIZER: Document {doc_id} update *command* sent to Firestore.---")
    print(f"--- FINALIZER: Document {doc_id} finalized. ---") # This print confirms the operation was attempted.
    
    # Clean up temporary sub-PDFs from GCS
    try:
        credentials = get_gcs_credentials()
        client = await asyncio.to_thread(gcs.Client, credentials=credentials)
        bucket = await asyncio.to_thread(client.bucket, DOCUMENTS_GCS_BUCKET_NAME)
        # Construct the prefix to list all sub-PDFs belonging to this original doc_id
        prefix = f"{doc_id}/{GCS_SUB_DOCS_FOLDER}/"
        # List_blobs is also blocking
        blobs_iterator = await asyncio.to_thread(bucket.list_blobs, prefix=prefix)
        
        deleted_count = 0
        # Iterate over blobs in a blocking way, then delete each one blocking
        for blob in blobs_iterator:
            await asyncio.to_thread(blob.delete)
            deleted_count += 1
        print(f"Cleaned up {deleted_count} temporary sub-PDFs for document {doc_id}.")
    except Exception as cleanup_e:
        print(f"Warning: Failed to clean up temporary sub-PDFs for {doc_id}: {cleanup_e}")


async def orchestrate_document_processing(
    doc_id_current_task: str, # This is the sub_doc_id if is_sub_document is True, else the original_doc_id
    file_path: str, # Local path to the downloaded PDF (full or sub-PDF)
    doc_data: Dict[str, Any], # The original doc_data (passed down consistently)
    is_sub_document: bool,
    original_doc_id: Optional[str] = None, # Only set if is_sub_document is True
    target_index: Optional[str] = "general",
    start_page_original: Optional[int] = None # Only set if is_sub_document is True
):
    """
    Orchestrates the page-by-page processing of a given PDF (either a full document or a sub-document chunk).
All progress and finalization are managed based on the `actual_parent_doc_id`.
"""
    db_client = None
    pdf_doc_to_process = None
    
    # Determine the actual document ID to update in Firestore (the main document)
    actual_parent_doc_id = original_doc_id if is_sub_document else doc_id_current_task

    # Define text-based file extensions
    TEXT_BASED_EXTENSIONS = ('.rtf', '.py', '.tf', '.c', '.cpp', '.json', '.yaml', '.yml', '.txt', '.md', '.csv', '.tsv')
    # Get the original filename from doc_data, not the temp file path
    original_filename = doc_data.get("fileName", "").lower()
    _, file_ext = os.path.splitext(original_filename)  # Extracts extension like '.tf', '.yml', etc.
    is_rtf = file_ext == '.rtf'
    is_text_file = file_ext in TEXT_BASED_EXTENSIONS and not is_rtf
    is_standalone_image = file_ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp']

    try:
        # Save credentials to a temporary file for this function's scope
        db_client = get_firestore_client()
        doc_ref = await asyncio.to_thread(db_client.collection('documents').document, actual_parent_doc_id)

        gemini_api_key = os.environ.get("GOOGLE_GEMINI_API_KEY") # Still needed if you want to use describe_image for metadata
        if not gemini_api_key:
            print("Warning: GOOGLE_GEMINI_API_KEY secret is not set. Image descriptions will not be generated if needed.")
            # raise ValueError("GOOGLE_GEMINI_API_KEY secret is not set.") # Removed as it's not critical for vectorization now

        company_id = doc_data.get('company')
        if not company_id:
            raise ValueError("Company ID is missing from doc_data.")
        sanitized_company_id = company_id.lower().replace('_', '-')

        # Sanitize and use the target_index from the payload, defaulting to 'general'.
        target_index_name = target_index or "general"
        sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index_name).lower()
        
        # --- Pinecone Setup for TWO Indexes ---
        text_index_name = f"techtalk-text-{sanitized_company_id}"
        image_index_name = f"techtalk-image-{sanitized_company_id}" # New index for images
        namespace = f"{sanitized_company_id}-{sanitized_target_index}"

        print(f"[PROCESSING_DEBUG] target_index parameter: '{target_index}'")
        print(f"[PROCESSING_DEBUG] sanitized_target_index: '{sanitized_target_index}'")
        print(f"[PROCESSING_DEBUG] text_index_name: '{text_index_name}'")
        print(f"[PROCESSING_DEBUG] image_index_name: '{image_index_name}'")
        print(f"[PROCESSING_DEBUG] namespace: '{namespace}'")

        pinecone_api_key = os.environ.get("PINECONE_API_KEY")
        if not pinecone_api_key:
            raise ValueError("PINECONE_API_KEY secret is not set.")

        # Initialize the Pinecone client using the cached getter, wrapped in to_thread
        # This ensures the client is initialized once and retrieved efficiently,
        # and the blocking operation is offloaded.
        pc = await asyncio.to_thread(get_pinecone_client, pinecone_api_key) # Use asyncio.to_thread for the blocking network calls

        existing_indexes_list = await asyncio.to_thread(pc.list_indexes)
        existing_index_names = [index.name for index in existing_indexes_list]

        # Check for and create TEXT index (768 dimensions)
        if text_index_name not in existing_index_names:
            print(f"Creating Pinecone text index: {text_index_name}")
            await asyncio.to_thread(
                pc.create_index,
                name=text_index_name,
                dimension=768,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        # Check for and create IMAGE index (1408 dimensions)
        if image_index_name not in existing_index_names:
            print(f"Creating Pinecone image index: {image_index_name}")
            await asyncio.to_thread(
                pc.create_index,
                name=image_index_name,
                dimension=1408,
                metric="dotproduct",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
        # Get the indexes
        text_index = await asyncio.to_thread(pc.Index, text_index_name) # Blocking call
        image_index = await asyncio.to_thread(pc.Index, image_index_name) # Blocking call 
        # FIXED: Wrap get_embeddings_model in asyncio.to_thread as it performs blocking I/O
        embeddings_model = await asyncio.to_thread(get_embeddings_model)

        # Open the current PDF (which is either the full original or a sub-PDF) ONCE
        #pdf_doc_to_process = await asyncio.to_thread(fitz.open, file_path) # Blocking call
        #total_pages_in_current_pdf_chunk = len(pdf_doc_to_process)

        # Set initial status message for this chunk's processing
        current_stage_message = f"Processing sub-document ({doc_id_current_task}) pages."if is_sub_document else "Processing document pages."

        # Initialize a list to hold all vectors (text and image) for batch upsert
        all_text_vectors_for_batch = []
        all_image_vectors_for_batch = []
        chunks_processed_in_this_task = 0
        
        if is_standalone_image:
            # Update status to processing
            await asyncio.to_thread(doc_ref.update, {
                "status": "processing",
                "progress": {"stage": "processing_image", "progress": 0, "message": "Processing standalone image..."},
                "lastModified": SERVER_TIMESTAMP
            })
            print(f"Updated Firestore status to 'processing' for standalone image {doc_id_current_task}.")
            
            # Process as standalone image
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            
            # Validate IDs don't contain path traversal (defense in depth)
            if '..' in company_id or '..' in actual_parent_doc_id:
                raise ValueError("Invalid path in company_id or document_id")
            
            # Create a single "page element" for the image
            gcs_image_name = f"companies/{company_id}/documents/{actual_parent_doc_id}/images/standalone_image.png"
            gcs_url = await upload_image_to_gcs(image_bytes, gcs_image_name)
            page_elements = [{
                "type": "image",
                "image_bytes": image_bytes,
                "metadata": {
                    "page_number": 1,
                    "gcs_url": gcs_url,
                }
            }]
            
            # Vectorize and get image vectors
            vectors_by_type = await vectorize_and_store_elements(
                actual_parent_doc_id,
                page_elements,
                doc_data,
                embeddings_model
            )
            
            all_image_vectors_for_batch.extend(vectors_by_type["image_vectors"])
            chunks_processed_in_this_task += len(vectors_by_type["image_vectors"])
            
            # Upsert to Pinecone
            if all_image_vectors_for_batch:
                await upsert_pinecone_batch_image(image_index, all_image_vectors_for_batch, namespace=namespace)
    
            # Finalize
            await task_finalize_document(doc_id_current_task)
            return JSONResponse(status_code=200, content={"message": "Standalone image processed successfully."})
            
        if is_rtf:
            print(f"Calling read_clean_rtf: {file_path}")
            current_stage_message = "Processing RTF document chunks."
            rtf_content = await asyncio.to_thread(read_and_clean_rtf, file_path)
            text_chunks = await asyncio.to_thread(chunk_text_by_token, rtf_content)
            total_pages_in_current_pdf_chunk = len(text_chunks)
            start_page_original = start_page_original if is_sub_document else 1
        elif is_text_file:
            print(f"Processing as plain text file: {file_path}")
            current_stage_message = "Processing text file chunks."
            text_content = await asyncio.to_thread(read_plain_text_file, file_path)
            text_chunks = await asyncio.to_thread(chunk_text_by_token, text_content)
            total_pages_in_current_pdf_chunk = len(text_chunks)
            start_page_original = start_page_original if is_sub_document else 1
        else:
            print(f"Calling fitzopen (PDF): {file_path}")
            current_stage_message = f"Processing sub-document ({doc_id_current_task}) pages."
            pdf_doc_to_process = await asyncio.to_thread(fitz.open, file_path)
            total_pages_in_current_pdf_chunk = len(pdf_doc_to_process)
            start_page_original = start_page_original if is_sub_document else 1
            

        # Update Firestore status to 'processing' and set subdocument status if applicable
        current_progress_message = f"Worker processing {'sub-document' if is_sub_document else 'document'} pages..."
        update_data = {
            "status": "processing",
            "progress": {"stage": current_stage_message, "progress": 0, "message": current_progress_message},
            "lastModified": SERVER_TIMESTAMP
        }
        if is_sub_document:
            # For sub-documents, update the subdocument_status map on the original document
            # Ensure the map exists and set the status for this specific sub_doc_id
            update_data[f"subdocument_status.{doc_id_current_task}"] = {
                "status": "processing",
                "processedAt": SERVER_TIMESTAMP,
                "progress": 0, # Progress for this specific sub-document
                "message": "Sub-document processing started."
            }
            # Also, mark the overall document as 'processing' if it's not already 'processed' or 'failed'
            # We fetch the current status to avoid overwriting a 'processed' status if this is a late-running subtask
            original_doc_snapshot = await asyncio.to_thread(doc_ref.get)
            if original_doc_snapshot.exists and original_doc_snapshot.get('status') not in ['processed', 'failed', 'permanently_failed']:
                await asyncio.to_thread(doc_ref.update, update_data)
            else:
                # If original doc is already finalized, just update the subdocument_status
                # This could happen if other subdocuments finished and finalized the parent
                await asyncio.to_thread(doc_ref.update({f"subdocument_status.{doc_id_current_task}": update_data[f"subdocument_status.{doc_id_current_task}"]}))
        else:
            # For main documents (not sub-documents), update its own status
            await asyncio.to_thread(doc_ref.update, update_data)

        print(f"Starting orchestration for {'sub-document' if is_sub_document else 'main document'} {doc_id_current_task}...")

        processing_start_time = time.time()
        for i in range(total_pages_in_current_pdf_chunk):
            page_number_in_current_chunk = i + 1 # 1-indexed
            
            print(f"Processing page {page_number_in_current_chunk}/{total_pages_in_current_pdf_chunk} of current chunk (Doc ID: {doc_id_current_task})...")

            # Process the page
            if is_rtf or is_text_file:
                    page_processing_result = await task_process_page_rtf(
                    original_doc_id=actual_parent_doc_id, # Always use the main doc ID for Pinecone
                    page_number_in_sub_pdf=page_number_in_current_chunk,
                    total_pages_in_sub_pdf=total_pages_in_current_pdf_chunk,
                    pdf_doc_sub=text_chunks[i],
                    doc_data=doc_data,
                    embeddings_model=embeddings_model,
                    start_page_original=start_page_original if is_sub_document else 1 # If not sub-doc, it starts at page 1
                )
            else:
                page_processing_result = await task_process_page(
                    original_doc_id=actual_parent_doc_id, # Always use the main doc ID for Pinecone
                    page_number_in_sub_pdf=page_number_in_current_chunk,
                    total_pages_in_sub_pdf=total_pages_in_current_pdf_chunk,
                    pdf_doc_sub=pdf_doc_to_process,
                    doc_data=doc_data,
                    embeddings_model=embeddings_model,
                    start_page_original=start_page_original if is_sub_document else 1 # If not sub-doc, it starts at page 1
                )
            
            all_text_vectors_for_batch.extend(page_processing_result["text_vectors"])
            all_image_vectors_for_batch.extend(page_processing_result["image_vectors"])
            chunks_processed_in_this_task += page_processing_result["chunks_created"]

            # --- Pinecone Batch Upsert Logic ---
            # Text vectors batching
            if len(all_text_vectors_for_batch) >= PINECONE_BATCH_SIZE:
                print(f"Upserting a batch of {len(all_text_vectors_for_batch)} text vectors...")
                await upsert_pinecone_batch_text(text_index, all_text_vectors_for_batch, namespace=namespace)
                all_text_vectors_for_batch = [] # Reset batch

            # Image vectors batching
            if len(all_image_vectors_for_batch) >= PINECONE_BATCH_SIZE:
                print(f"Upserting a batch of {len(all_image_vectors_for_batch)} image vectors...")
                await upsert_pinecone_batch_image(image_index, all_image_vectors_for_batch, namespace=namespace)
                all_image_vectors_for_batch = [] # Reset batch

            # Update progress in Firestore more frequently for longer tasks
            progress_percent = int(((i + 1) / total_pages_in_current_pdf_chunk) * 100)
            progress_message = f"Processed page {i + 1} of {total_pages_in_current_pdf_chunk}."
            
            update_data = {
                "progress": {"stage": current_stage_message, "progress": progress_percent, "message": progress_message},
                "lastModified": SERVER_TIMESTAMP
            }
            if is_sub_document:
                update_data[f"subdocument_status.{doc_id_current_task}.progress"] = progress_percent
                update_data[f"subdocument_status.{doc_id_current_task}.message"] = progress_message
                await asyncio.to_thread(doc_ref.update, update_data)
            else:
                await asyncio.to_thread(doc_ref.update, update_data)
            print(f"Updated progress to {progress_percent}% for {doc_id_current_task}.")

        # Upsert any remaining vectors in the batch after the loop
        if all_text_vectors_for_batch:
            print(f"Upserting remaining {len(all_text_vectors_for_batch)} text vectors...")
            await upsert_pinecone_batch_text(text_index, all_text_vectors_for_batch, namespace=namespace)

        if all_image_vectors_for_batch:
            print(f"Upserting remaining {len(all_image_vectors_for_batch)} image vectors...")
            await upsert_pinecone_batch_image(image_index, all_image_vectors_for_batch, namespace=namespace)

        processing_end_time = time.time()
        processing_duration = processing_end_time - processing_start_time
        print(f"Orchestration for {doc_id_current_task} completed in {processing_duration:.2f} seconds.")

        # --- Finalize status update ---
        if not is_sub_document:
            # Only the main document's orchestration should call finalize for itself.
            # Sub-documents completion is tracked in the subdocument_status map.
            await task_finalize_document(doc_id_current_task)
            # Increment a counter for total chunks processed on the main document
            await asyncio.to_thread(doc_ref.update, {"totalChunksProcessed": Increment(chunks_processed_in_this_task)})
            
            print(f"Main document {doc_id_current_task} processing finished. Total chunks: {chunks_processed_in_this_task}")
        else:
            # For sub-documents, update their specific entry in the parent document's subdocument_status map
            print(f"Sub-document {doc_id_current_task} processing finished. Updating parent status.")
            update_data = {
                f"subdocument_status.{doc_id_current_task}.status": "completed",
                f"subdocument_status.{doc_id_current_task}.processedAt": SERVER_TIMESTAMP,
                f"subdocument_status.{doc_id_current_task}.progress": 100,
                f"subdocument_status.{doc_id_current_task}.message": "Sub-document processed successfully."
            }
            # Increment the totalChunksProcessed on the original document
            update_data["totalChunksProcessed"] = Increment(chunks_processed_in_this_task)
            await asyncio.to_thread(doc_ref.update, update_data)
            
            print(f"Sub-document {doc_id_current_task} status updated to 'completed' on parent {actual_parent_doc_id}.")
            
        return JSONResponse(status_code=200, content={"message": f"Document {'sub-document' if is_sub_document else 'main document'} {doc_id_current_task} processed successfully."})

    except Exception as e:
        error_message = f"Critical orchestration error for {'sub-document' if is_sub_document else 'main document'} {doc_id_current_task}: {str(e)}"
        print(f" {error_message}")
        traceback.print_exc()

        if db_client and doc_ref:
            try:
                # Update main document status to failed
                update_data = {
                    "status": "failed",
                    "lastError": error_message,
                    "failedAt": SERVER_TIMESTAMP,
                    "progress": {"stage": "error", "progress": 0, "message": "Orchestration failed."}
                }
                if is_sub_document:
                    # Update the specific subdocument's status within the parent
                    update_data[f"subdocument_status.{doc_id_current_task}.status"] = "failed"
                    update_data[f"subdocument_status.{doc_id_current_task}.lastError"] = error_message
                    update_data[f"subdocument_status.{doc_id_current_task}.failedAt"] = SERVER_TIMESTAMP
                    update_data[f"subdocument_status.{doc_id_current_task}.message"] = "Sub-document processing failed."
                
                await asyncio.to_thread(doc_ref.update, update_data)
                print(f"Firestore status for {actual_parent_doc_id} updated to 'failed' due to orchestration error.")
            except Exception as firestore_e:
                print(f"Failed to update Firestore status to 'failed' for {actual_parent_doc_id}: {firestore_e}")
        
        raise HTTPException(status_code=500, detail=f"Orchestration failed: {e}") from e
    finally:
        if pdf_doc_to_process:
            await asyncio.to_thread(pdf_doc_to_process.close) # Ensure the PDF is closed

@router.post("/process-document-worker")
async def process_document_worker(payload: WorkerPayload):
    """
    This is the main entry point for the document processing worker.
    It's triggered by an HTTP request (e.g., from a Cloud Task or another service).
    """
    doc_id = payload.doc_id
    file_url = payload.file_url
    temp_pdf_path = None
    file_extension = '.pdf'
    
    db_client = None # Initialize db_client outside try for finally block access
    original_doc_ref = None # Initialize original_doc_ref

    current_task_doc_ref = None # Reference to the document that holds retryCount for this specific task (main or sub)

    try:
        db_client = get_firestore_client()
        
        # CRITICAL CHANGE START: Retry Logic and Status Management
        original_doc_ref = await asyncio.to_thread(db_client.collection('documents').document, payload.original_doc_id)
        current_task_doc_ref = await asyncio.to_thread(db_client.collection('documents').document, doc_id) # This is the doc for *this specific task* (sub-doc or main doc)

        # Fetch current retry count for THIS task (sub-doc or main doc)
        current_task_doc_snapshot = await asyncio.to_thread(current_task_doc_ref.get)
        
        # Check if document still exists (may have been deleted before worker ran)
        if not current_task_doc_snapshot.exists:
            print(f"Worker for {doc_id}: Document no longer exists. Skipping processing.")
            return JSONResponse(content={"status": "skipped", "reason": "document_deleted", "doc_id": doc_id})

        current_task_doc_data = current_task_doc_snapshot.to_dict()
        current_status = current_task_doc_data.get('status')
        current_retry_count = current_task_doc_data.get('retryCount', 0)
        processed_at = current_task_doc_data.get('processedAt')

        print(f"Worker for {doc_id} (original: {payload.original_doc_id}) started. Current retry count: {current_retry_count}")

        # FIX: Check if document is already in terminal state
        # Return 200 to Cloud Tasks to stop retries
        if current_status in ['processed', 'permanently_failed']:
            print(f"Worker for {doc_id}: Already in terminal state '{current_status}'. Skipping processing.")
            return JSONResponse(content={
                "status": "skipped",
                "reason": f"document_already_{current_status}",
                "doc_id": doc_id
            })
        
        # Also check if document was already processed (has processedAt timestamp)
        if processed_at is not None:
            print(f"Worker for {doc_id}: Already processed at {processed_at}. Skipping processing.")
            return JSONResponse(content={
                "status": "skipped",
                "reason": "document_already_processed",
                "doc_id": doc_id,
                "processedAt": str(processed_at)
            })

        # FIX: If retry count exceeded, return 200 instead of raising HTTPException
        if current_retry_count >= MAX_RETRIES:
            print(f"Worker for {doc_id} exceeded max retries ({MAX_RETRIES}). Marking as permanently_failed.")
            # Mark the current task (sub-doc or main doc) as permanently_failed
            await asyncio.to_thread(current_task_doc_ref.update, {
                "status": "permanently_failed",
                "lastError": f"Exceeded maximum retries ({MAX_RETRIES}).",
                "failedAt": SERVER_TIMESTAMP,
                "retryCount": Increment(1) # Still increment to reflect the final attempt
            })
            if payload.is_sub_document:
                # Update the parent document's subdocument_status map
                sub_doc_status_path = f"subdocument_status.{doc_id}"
                await asyncio.to_thread(original_doc_ref.update, {
                    f"{sub_doc_status_path}.status": "permanently_failed",
                    f"{sub_doc_status_path}.lastError": f"Sub-document exceeded maximum retries ({MAX_RETRIES}).",
                    f"{sub_doc_status_path}.failedAt": SERVER_TIMESTAMP
                })
            # Return 200 to stop Cloud Tasks retries
            return JSONResponse(content={
                "status": "failed",
                "reason": "max_retries_exceeded",
                "doc_id": doc_id,
                "retryCount": current_retry_count
            })

        # Increment retryCount at the beginning of a valid attempt
        # This records that an attempt was made.
        await asyncio.to_thread(current_task_doc_ref.update, {"retryCount": Increment(1)})
        print(f"Incremented retryCount for {doc_id} to {current_retry_count + 1}.")

        if payload.is_sub_document:
            sub_doc_status_path = f"subdocument_status.{doc_id}"
            await asyncio.to_thread(original_doc_ref.update, {
                f"{sub_doc_status_path}.status": "processing",
                f"{sub_doc_status_path}.startedAt": SERVER_TIMESTAMP,
                f"{sub_doc_status_path}.message": "Sub-document worker started processing."
            })
            print(f"Sub-document status for {doc_id} set to 'processing' on parent {payload.original_doc_id}.")

        # Download the PDF from GCS
        credentials = get_gcs_credentials()
        client = await asyncio.to_thread(gcs.Client, credentials=credentials)
        bucket_name = DOCUMENTS_GCS_BUCKET_NAME
        file_path_in_gcs = file_url.split(f"/{bucket_name}/")[-1]

        bucket = await asyncio.to_thread(client.get_bucket, bucket_name)
        blob = await asyncio.to_thread(bucket.blob, file_path_in_gcs)
        
        #fd_pdf, temp_pdf_path = await asyncio.to_thread(tempfile.mkstemp, suffix=".pdf")

        MIME_TO_EXTENSION = {
            'text/x-python': '.py',
            'text/x-terraform': '.tf',
            'text/x-c': '.c',
            'text/x-c++': '.cpp',
            'text/x-cpp': '.cpp',
            'application/json': '.json',
            'text/yaml': '.yaml',
            'text/x-yaml': '.yml',
            'text/rtf': '.rtf',
            'application/pdf': '.pdf',
            'text/plain': '.txt',
            'text/markdown': '.md',
        }

        # --- ROBUST FILE EXTENSION LOGIC (Explicit MIME Type Mapping) ---
        raw_file_type = payload.doc_data.get('fileType', '').lower()
        
        # Default to PDF since most documents are expected to be PDFs
        # This variable MUST be set to a string that starts with a dot (e.g., .pdf)
        # file_extension = '.pdf' 
        file_extension = MIME_TO_EXTENSION.get(raw_file_type)


        # Explicit mapping for common types to eliminate the slash from MIME types
        #if raw_file_type == 'text/rtf' or raw_file_type == 'rtf':
        #    file_extension = '.rtf'
        #elif raw_file_type == 'text/.rtf' or raw_file_type == '.rtf':
        #    file_extension = '.rtf'
        #elif raw_file_type == 'application/pdf' or raw_file_type == 'pdf' or raw_file_type == '.pdf':
        #    file_extension = '.pdf'
        # Fallback for any other MIME type that contains a slash (defensive measure)
        #elif '/' in raw_file_type:
        #    # Safely extract the extension part (e.g., 'jpeg' from 'image/jpeg')
        #    ext = raw_file_type.split('/')[-1]
        #    file_extension = f'.{ext}'

        if not file_extension:
            # Fallback logic
            if '/' in raw_file_type:
                ext = raw_file_type.split('/')[-1]
                file_extension = f'.{ext}'
            else:
                file_extension = '.pdf'  # Default
        # file_extension is now guaranteed to be a safe string starting with '.'
            
        print(f"Temporary file suffix determined as: {file_extension} (based on input: {raw_file_type})")
        
        fd_pdf, temp_pdf_path = await asyncio.to_thread(tempfile.mkstemp, suffix=file_extension)
        # -------------------------------------
        
        await asyncio.to_thread(os.close, fd_pdf) # Close immediately
        await asyncio.to_thread(blob.download_to_filename, temp_pdf_path) # Blocking GCS download
        print(f"Downloaded GCS file {file_path_in_gcs} to {temp_pdf_path}")

        # Call the orchestrator
        await orchestrate_document_processing(
            doc_id_current_task=doc_id,
            file_path=temp_pdf_path,
            doc_data=payload.doc_data,
            is_sub_document=payload.is_sub_document,
            original_doc_id=payload.original_doc_id,
            target_index=payload.target_index,
            start_page_original=payload.start_page_original
        )

        return JSONResponse(status_code=200, content={"message": f"Worker successfully processed {doc_id}"})

    except HTTPException as http_e: # Re-raise HTTPExceptions directly without changing status
        print(f"Caught HTTP Exception in worker for {doc_id}: {http_e.detail}")
        raise http_e
    except Exception as e:
        print(f"Worker processing failed for {doc_id}: {e}")
        traceback.print_exc()

        if db_client and current_task_doc_ref:
            try:
                # Update status of the current task (sub-doc or main doc) to failed
                await asyncio.to_thread(current_task_doc_ref.update, {
                    "status": "failed",
                    "lastError": f"Worker error: {str(e)}",
                    "failedAt": SERVER_TIMESTAMP,
                    "retryCount": Increment(1)
                })
                print(f"Firestore status for current task {doc_id} updated to 'failed' due to worker error.")

                if payload.is_sub_document and original_doc_ref:
                    sub_doc_status_path = f"subdocument_status.{doc_id}"
                    await asyncio.to_thread(original_doc_ref.update, {
                        f"{sub_doc_status_path}.status": "failed",
                        f"{sub_doc_status_path}.lastError": f"Sub-document worker error: {str(e)}",
                        f"{sub_doc_status_path}.failedAt": SERVER_TIMESTAMP
                    })
                    print(f"Firestore subdocument_status for {doc_id} updated to 'failed' on parent {payload.original_doc_id}.")

            except Exception as firestore_e:
                print(f"Failed to update Firestore status to 'failed' for {doc_id}: {firestore_e}")

        # This will still raise 500 for Cloud Tasks if current_retry_count was < MAX_RETRIES
        raise HTTPException(status_code=500, detail=f"Worker processing failed: {e}") from e
    finally:
        if temp_pdf_path and await asyncio.to_thread(os.path.exists, temp_pdf_path):
            await asyncio.to_thread(os.remove, temp_pdf_path)
            print(f"Cleaned up temporary PDF file: {temp_pdf_path}")
