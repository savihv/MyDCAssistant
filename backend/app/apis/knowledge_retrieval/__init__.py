from fastapi import APIRouter, HTTPException, Body, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
import databutton as db
import os
import json
import traceback
import asyncio
import re
from app.libs.constraint_manager import get_active_constraints, format_constraints_for_gemini
import time
from datetime import datetime

from google.cloud import storage  # type: ignore
from google.cloud.firestore import Client as FirestoreClient, SERVER_TIMESTAMP  # type: ignore

from pinecone import Pinecone  # type: ignore

from app.apis.doc_processor import get_embeddings_model, MultimodalEmbeddingAdapter

from app.auth import AuthorizedUser
from app.libs.auth_helpers import verify_internal_worker_request
from app.libs.intent_router import IntentRouter
from app.libs.comparative_analyzer import ComparativeAnalyzer
from app.libs.firebase_config import get_firestore_client, get_firebase_credentials_dict
from google.oauth2 import service_account  # type: ignore
from app.libs.namespace_utils import (
    get_company_namespaces, 
    get_default_namespace,
    get_intent_to_namespaces_mapping
)
from app.libs.gemini_client import get_gemini_client


router = APIRouter() # RESTORED ROUTER

# --- Pydantic Models ---
class RetrievalRequest(BaseModel):
    query: str
    company: str
    max_results: int = 5
    score_threshold: Optional[float] = None
    media_urls: Optional[List[str]] = None # Accept image URLs
    namespaces: Optional[List[str]] = None # ✅ ADD THIS - User's explicit namespace selection
    

class Chunk(BaseModel):
    id: str
    documentId: str
    content: str
    metadata: Dict[str, Any]
    score: float
    source_index: Optional[str] = None 
    image_embedding: Optional[List[float]] = None
    text_embedding: Optional[List[float]] = None

class RetrievalResponse(BaseModel):
    chunks: List[Chunk] = Field(..., description="Retrieved document chunks")
    query: str = Field(..., description="Original query")

class NamespaceInfo(BaseModel):
    id: str
    displayName: str
    isDefault: bool = False

class CompanyNamespacesResponse(BaseModel):
    namespaces: List[NamespaceInfo]

# --- Helper function to get GCS client, memoized for efficiency ---
def _get_gcs_client():
    try:
        creds_dict = get_firebase_credentials_dict()
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        return storage.Client(credentials=creds)
    except Exception as e:
        print(f"[RAG_DEBUG] ERROR: Failed to initialize GCS client. Reason: {e}")
        return None

def _get_query_embeddings(
    request: RetrievalRequest, 
    embedding_adapter: MultimodalEmbeddingAdapter # Use the adapter
) -> Tuple[Optional[List[float]], Optional[List[float]]]: 
    """
    Generates embeddings for the user's query using the shared embedding adapter.
    - Text embedding is always generated from request.query.
    - Image embedding is generated from the first URL in request.media_urls, if available.
    """
    print("[RAG_DEBUG] ==> ENTERING _get_query_embeddings")
    
    # 1. Generate text embedding (always)
    try:
        # Use the adapter's method
        text_embedding = embedding_adapter.embed_text([request.query])[0]
        print(f"[RAG_DEBUG] Successfully generated text embedding from query: '{request.query[:50]}...'")
    except Exception as e:
        print(f"[RAG_DEBUG] ERROR: Failed to generate text embedding. Reason: {e}")
        text_embedding = None

    # 2. Generate image embedding (only if media_urls are provided)
    image_embedding = None
    if request.media_urls:
        print(f"[RAG_DEBUG] media_urls detected. Attempting to generate image embedding from URL: {request.media_urls[0]}")
        # --- THIS IS THE KEY CHANGE ---
        # Instead of embedding text, we download the image and embed the image data
        gcs_client = _get_gcs_client()
        if not gcs_client:
            print("[RAG_DEBUG] Could not initialize GCS client, skipping image embedding generation from URL.")
            return text_embedding, None

        try:
            image_url = request.media_urls[0]
            if not image_url.startswith("gs://"):
                raise ValueError("Invalid GCS URL format. Must start with gs://")

            bucket_name, blob_name = image_url.replace("gs://", "").split("/", 1)
            blob = gcs_client.bucket(bucket_name).blob(blob_name)
            image_bytes = blob.download_as_bytes()
            
            # Use the adapter to embed the downloaded image bytes
            image_embedding = embedding_adapter.embed_image(image_bytes)
            print(f"[RAG_DEBUG] Successfully generated image embedding from technician's photo.{image_url}")
        
        except Exception as e:
            print(f"[RAG_DEBUG] ERROR: Failed to generate image embedding from URL '{request.media_urls[0]}'. Reason: {e}")
            print(traceback.format_exc())
            # Fallback to None, so the process can continue with text search
            image_embedding = None
    else:
        print("[RAG_DEBUG] No media_urls provided. Skipping image embedding generation for query.")

    print("[RAG_DEBUG] ==> EXITING _get_query_embeddings")
    return text_embedding, image_embedding

def generate_summary(
    query: str, 
    chunks: list, 
    intent: str, 
    technician_data: Optional[str] = None,  # ✅ Explicitly Optional
    constraints: Optional[str] = None        # ✅ Explicitly Optional
) -> str:
    """
    Generates a summary using an LLM based on retrieved chunks.
    
    Args:
        query: User's query
        chunks: Retrieved chunks
        intent: Detected intent from router
        technician_data: Raw uploaded file content (optional)
        constraints: Formatted constraints to inject into system instruction (optional)
    """
    # If intent is baseline_comparison, use the comparative analyzer
    if intent == "baseline_comparison":
        print("[SUMMARY_DEBUG] Using comparative analyzer for baseline comparison")
        
        # Separate chunks by source
        general_chunks = [c for c in chunks if c.get("source_index") == "general"]
        baseline_chunks = [c for c in chunks if c.get("source_index") == "baseline"]
        
        print(f"[SUMMARY_DEBUG] General chunks: {len(general_chunks)}, Baseline chunks: {len(baseline_chunks)}")
        
        if not baseline_chunks:
            return """⚠️ **No baseline data found for comparison.**

I couldn't find any reference baseline documents for this equipment in the knowledge base. 

To perform a proper baseline comparison, please ask your administrator to:
1. Navigate to the "Baseline Knowledge Management" section
2. Upload reference documents showing correct configurations, logs, or telemetry for this equipment type

In the meantime, I can provide general troubleshooting assistance. Would you like me to search for general information about this issue instead?"""
        
        # Use the comparative analyzer
        analyzer = ComparativeAnalyzer()
        return analyzer.analyze(query, general_chunks, baseline_chunks, technician_data, constraints)
    
    try:
        llm_model = get_gemini_client()
    except Exception as e:
        print(f"Error configuring Gemini: {e}")
        llm_model = None

    if not llm_model:
        return "LLM model is not configured. Cannot generate summary."

    # Safely gather text from text-based chunks
    print(f"[SUMMARY_DEBUG] Received {len(chunks)} chunks for summary generation.")
    print(f"[SUMMARY_DEBUG] All chunks received: {chunks}")
    context_lines = []
    for i, chunk in enumerate(chunks):
        print(f"--- [SUMMARY_DEBUG] Processing chunk {i+1}/{len(chunks)} ---")
        metadata = chunk.get("metadata", {})
        chunk_type = metadata.get("type")
        source = metadata.get("source")
        source_index = chunk.get("source_index")
        
        content_to_add = None
        
        # Priority 1: Standard Text Chunks
        if chunk_type == "text" and chunk.get("content"):
            content_to_add = chunk["content"]
            
        # Priority 2: Expert Sessions (often have type=None but content in summary_text)
        elif source == "technician_session":
            content_to_add = metadata.get("summary_text") or chunk.get("content")
            if content_to_add:
                content_to_add = f"[Expert Session Log]: {content_to_add}"
                
        # Priority 3: Historic Records (CSV imports) or Expert Tips
        # These might lack 'type' but have content or original_text
        elif source_index in ["historic", "expert"] or metadata.get("source") in ["expert_tip", "historic_record"]:
             # Try explicit content first
             if chunk.get("content") and chunk.get("content") != "Content not available.":
                 content_to_add = chunk["content"]
             # Fallback to original_text in metadata if content is missing/placeholder
             elif metadata.get("original_text"):
                 content_to_add = metadata.get("original_text")
        
        # Priority 4: Fallback for any chunk with readable text content
        elif chunk.get("content") and chunk.get("content") != "Content not available.":
            content_to_add = chunk["content"]

        if content_to_add:
            context_lines.append(content_to_add)
            print("[SUMMARY_DEBUG] APPENDED chunk to context.")
        else:
            print(f"[SUMMARY_DEBUG] SKIPPED chunk. Type: {chunk_type}, Source: {source}, Index: {source_index}")


    context = "\n\n---\n\n".join(context_lines)
    print(f"[SUMMARY_DEBUG] Final context for LLM: '{context[:200]}...'")

    # If context is empty but chunks were found, it means we only found images.
    if not context and chunks:
        return "I found relevant images in the knowledge base but no accompanying text to summarize. Please check the provided sources for more details."

    # If context is empty and there were no chunks, the LLM will handle it.

    # Build base prompt
    base_prompt = """
    Based on the following context, provide a clear and concise answer to the user's question.
    Act as a helpful senior technician assisting a junior colleague.
    If the context does not contain enough information, state that you couldn't find a specific answer in the knowledge base.
    """
    
    # Inject constraints if available
    if constraints:
        print(f"[CONSTRAINT_DEBUG] Injecting constraints into system instruction: {constraints[:200]}...")
        base_prompt += f"\n\n{constraints}\n"
    
    prompt = f"""{base_prompt}

    **Context:**
    {context}

    **Question:** {query}

    **Answer:**
    """
    try:
        response = llm_model.generate_content(prompt, model='gemini-2.5-flash')
        return response
    except Exception as e:
        print(f"Error generating summary with LLM: {e}")
        return "There was an error generating the summary."


# --- Function to retrieve relevant document chunks from vector database ---
def retrieve_document_chunks(
    request: RetrievalRequest,
    user_data: dict
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Retrieve relevant document chunks from vector database based on query
    and user's company/organization access rights
    
    Returns:
        Tuple of (chunks, intent_result)
    """
    print("[RAG_DEBUG] ==> ENTERING retrieve_document_chunks")
    print(f"[RAG_DEBUG] Query: '{request.query[:100]}...'")
    print(f"[RAG_DEBUG] User Company: {user_data.get('company')}, Max Results: {request.max_results}, Score Threshold: {request.score_threshold}")

    user_company = user_data.get('company')
    intent_router = IntentRouter(company_id=user_company)
    has_uploaded_file = request.media_urls is not None and len(request.media_urls) > 0

    # ✅ CHANGED: Check if explicit namespaces are provided by user
    if request.namespaces:
        # User explicitly selected namespaces - map them
        print(f"[RAG_DEBUG] User provided explicit namespaces: {request.namespaces}")
        
        # Get dynamic namespaces and intent mapping
        user_company = user_data.get('company')
        available_namespaces = get_company_namespaces(user_company)
        intent_mapping = get_intent_to_namespaces_mapping(user_company)
        
        # Dynamic mapping - map each namespace ID to itself
        namespace_mapping = {}
        for ns_id in available_namespaces:
            namespace_mapping[ns_id] = ns_id
        
        # Add "all" option using multi intent mapping
        namespace_mapping["all"] = intent_mapping.get("multi", available_namespaces)
        
        print(f"[RAG_DEBUG] Namespace mapping for explicit selection: {namespace_mapping}")
    
        # Handle the mapping - expand "all" to multiple namespaces
        target_indexes = []
        for ns in request.namespaces:
            mapped = namespace_mapping.get(ns, ns)
            if isinstance(mapped, list):
                # "all" case - expand to all namespaces
                target_indexes.extend(mapped)
            else:
                target_indexes.append(mapped)
        
        print(f"[RAG_DEBUG] Mapped to target indexes: {target_indexes}")
    
        # Set a default intent for logging purposes
        intent_result = {"intent": "user_selected", "confidence": 1.0}
    else:
        # No explicit namespaces - use Intent Router (AI detection)
        intent_result = intent_router.classify(request.query, has_uploaded_file)
        print(f"[INTENT_ROUTER] Result: {intent_result}")
    
        detected_intent = intent_result["intent"]
        print(f"[INTENT_ROUTER] Detected intent: {detected_intent}")
    
        # Get dynamic intent-to-namespace mapping from company settings
        user_company = user_data.get('company')
        intent_to_indexes = get_intent_to_namespaces_mapping(user_company)
        default_namespace = get_default_namespace(user_company)
        
        # Get target indexes based on detected intent
        target_indexes = intent_to_indexes.get(detected_intent, [default_namespace])
        print(f"[RAG_DEBUG] Intent '{detected_intent}' mapped to namespaces: {target_indexes}")
        print(f"[RAG_DEBUG] Full intent mapping: {intent_to_indexes}")

    try:
        # Get Pinecone API key
        pinecone_api_key = os.environ.get("PINECONE_API_KEY")
        if not pinecone_api_key:
            print("[RAG_DEBUG] ERROR: Pinecone API key not found")
            raise ValueError("Pinecone API key not found")

        # --- CORRECTED: Use the shared embedding adapter ---
        embedding_adapter = get_embeddings_model()
        
        # Generate embeddings using the helper function and the adapter
        text_query_embedding, image_query_embedding = _get_query_embeddings(
            request=request,
            embedding_adapter=embedding_adapter,
        )
        
        # Initialize Pinecone client
        pc = Pinecone(api_key=pinecone_api_key)
        
        user_company = user_data.get('company')
        if not user_company:
            print("[RAG_DEBUG] ERROR: User has no company. Cannot determine Pinecone index.")
            return [], intent_result

        # This namespace must match the one used during the upsert in doc_processor
        sanitized_company_id = user_company.lower().replace('_', '-')
        print(f"[RAG_DEBUG] Target Namespace: {sanitized_company_id}")

        
        all_matches = []
        # filter_dict = {} # Define filter dict (currently empty for admins)
        
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        
        text_index_name = f"techtalk-text-{sanitized_company_id}"
        image_index_name = f"techtalk-image-{sanitized_company_id}"
            
        # Check if global indexes exist
        if text_index_name not in existing_indexes:
            print(f"[RAG_DEBUG] WARNING: Global text index '{text_index_name}' does not exist")
        if image_index_name not in existing_indexes:
            print(f"[RAG_DEBUG] WARNING: Global image index '{image_index_name}' does not exist")

        # Get index objects once
        text_index = pc.Index(text_index_name) if text_index_name in existing_indexes else None
        image_index = pc.Index(image_index_name) if image_index_name in existing_indexes else None


        # NEW: Loop through each target index
        for target_index in target_indexes:
            sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index).lower()
            namespace = f"{sanitized_company_id}-{sanitized_target_index}"
            
            print(f"[RAG_DEBUG] Querying target_index: {target_index}")
            print(f"[RAG_DEBUG]   Namespace: {namespace}")
    
            # Query TEXT index for this target with retry logic
            if text_query_embedding and text_index:
                max_retries = 3  # 1 initial attempt + 2 retries
                retry_delay = 0.3  # 300ms between attempts
                
                for attempt in range(max_retries):
                    try:
                        text_response = text_index.query(
                            vector=text_query_embedding,
                            top_k=request.max_results,
                            include_metadata=True,
                            namespace=namespace,
                            filter=None
                        )
                        
                        # Check if we got results or if we should retry
                        if len(text_response.matches) > 0 or attempt == max_retries - 1:
                            # Got results or final attempt - process and break
                            for match in text_response.matches:
                                match.metadata["source_index"] = target_index
                            
                            scores = [m.score for m in text_response.matches]
                            above_threshold = [s for s in scores if s >= request.score_threshold]
                            
                            if attempt > 0 and len(text_response.matches) > 0:
                                print(f"[RAG_DEBUG]   ✅ Retry successful on attempt {attempt + 1}")
                            
                            print(f"[RAG_DEBUG]   Found {len(text_response.matches)} text matches (scores: {scores})")
                            print(f"[RAG_DEBUG]   After threshold {request.score_threshold}: {len(above_threshold)} matches (scores: {above_threshold})")
                            
                            all_matches.extend(text_response.matches)
                            break
                        else:
                            # Got 0 results but not final attempt - retry
                            print(f"[RAG_DEBUG]   ⚠️ Got 0 results on attempt {attempt + 1}, retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            
                    except Exception as e:
                        if attempt == max_retries - 1:
                            print(f"[RAG_DEBUG]   ERROR querying text index with namespace {namespace}: {e}")
                        else:
                            print(f"[RAG_DEBUG]   ⚠️ Error on attempt {attempt + 1}: {e}, retrying...")
                            time.sleep(retry_delay)
            
            # Query IMAGE index for this target with retry logic
            if image_query_embedding and image_index:
                max_retries = 3  # 1 initial attempt + 2 retries
                retry_delay = 0.3  # 300ms between attempts
                
                for attempt in range(max_retries):
                    try:
                        image_response = image_index.query(
                            vector=image_query_embedding,
                            top_k=request.max_results,
                            include_metadata=True,
                            namespace=namespace,
                            filter=None
                        )
                        
                        if len(image_response.matches) > 0 or attempt == max_retries - 1:
                            for match in image_response.matches:
                                match.metadata["source_index"] = target_index
                            
                            scores = [m.score for m in image_response.matches]
                            above_threshold = [s for s in scores if s >= request.score_threshold]
                            
                            if attempt > 0 and len(image_response.matches) > 0:
                                print(f"[RAG_DEBUG]   ✅ Image retry successful on attempt {attempt + 1}")
                            
                            print(f"[RAG_DEBUG]   Found {len(image_response.matches)} image matches (scores: {scores})")
                            print(f"[RAG_DEBUG]   After threshold {request.score_threshold}: {len(above_threshold)} matches (scores: {above_threshold})")
                            
                            all_matches.extend(image_response.matches)
                            break
                        else:
                            print(f"[RAG_DEBUG]   ⚠️ Got 0 image results on attempt {attempt + 1}, retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            
                    except Exception as e:
                        if attempt == max_retries - 1:
                            print(f"[RAG_DEBUG]   ERROR querying image index with namespace {namespace}: {e}")
                        else:
                            print(f"[RAG_DEBUG]   ⚠️ Image error on attempt {attempt + 1}: {e}, retrying...")
                            time.sleep(retry_delay)
            else:
                if not image_query_embedding:
                    print("[RAG_DEBUG] SKIPPING Image index query because embedding could not be generated.")
                else:
                    print(f"[RAG_DEBUG] WARNING: Image index '{image_index_name}' not found.")
        
        # MOVED OUTSIDE LOOP: Sort all combined matches by score
        print(f"[RAG_DEBUG] Found a total of {len(all_matches)} matches before sorting and filtering.")
        all_matches.sort(key=lambda x: x.score, reverse=True)
        
        # Extract and filter results by score threshold
        chunks = []
        seen_ids = set()
        for match in all_matches:
            if match.id not in seen_ids and match.score >= request.score_threshold:
                chunks.append({
                    "id": match.id,
                    "documentId": match.metadata.get("document_id", ""),
                    "score": match.score,
                    "metadata": match.metadata,
                    "content": "", # Content will be fetched from Firestore next
                    "source_index": match.metadata.get("source_index", "unknown")
                })
                seen_ids.add(match.id)
        
        print(f"[RAG_DEBUG] Returning {len(chunks)} unique chunks after score filtering (threshold: {request.score_threshold}).")
        
        # ✅ CASCADE FALLBACK: If intent-specific search yielded 0 results, expand to all namespaces
        if not chunks and not request.namespaces and intent_result["intent"] != "multi":
            print(f"[FALLBACK] Intent '{intent_result['intent']}' returned 0 chunks. Expanding search to ALL namespaces...")
            
            # Calculate fallback threshold (20% lower = 80% of original)
            fallback_threshold = request.score_threshold * 0.8  # 0.5 * 0.8 = 0.4
            print(f"[FALLBACK] Using fallback threshold: {fallback_threshold} (80% of primary {request.score_threshold})")
            
            # Try searching across ALL namespaces
            # Use "multi" intent mapping for fallback (searches all configured namespaces)
            intent_mapping = get_intent_to_namespaces_mapping(user_company)
            fallback_indexes = intent_mapping.get("multi", get_company_namespaces(user_company))
            print(f"[FALLBACK] Using fallback namespaces: {fallback_indexes}")
            all_matches_fallback = []
            
            for target_index in fallback_indexes:
                sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index).lower()
                namespace = f"{sanitized_company_id}-{sanitized_target_index}"
                
                print(f"[FALLBACK]   Querying namespace: {namespace}")
                
                # Query TEXT index
                if text_query_embedding and text_index:
                    try:
                        text_response = text_index.query(
                            vector=text_query_embedding,
                            top_k=request.max_results,
                            include_metadata=True,
                            namespace=namespace,
                            filter=None
                        )
                        for match in text_response.matches:
                            match.metadata["source_index"] = target_index
                        
                        # DEBUG: Show scores before filtering
                        scores = [m.score for m in text_response.matches]
                        above_threshold = [s for s in scores if s >= fallback_threshold]
                        print(f"[FALLBACK]     Found {len(text_response.matches)} text matches (scores: {scores})")
                        print(f"[FALLBACK]     After threshold {fallback_threshold}: {len(above_threshold)} matches (scores: {above_threshold})")
                        
                        all_matches_fallback.extend(text_response.matches)
                    except Exception as e:
                        print(f"[FALLBACK]     ERROR querying text: {e}")
                
                # Query IMAGE index
                if image_query_embedding and image_index:
                    try:
                        image_response = image_index.query(
                            vector=image_query_embedding,
                            top_k=request.max_results,
                            include_metadata=True,
                            namespace=namespace,
                            filter=None
                        )
                        for match in image_response.matches:
                            match.metadata["source_index"] = target_index
                        
                        # DEBUG: Show scores before filtering
                        scores = [m.score for m in image_response.matches]
                        above_threshold = [s for s in scores if s >= fallback_threshold]
                        print(f"[FALLBACK]     Found {len(image_response.matches)} image matches (scores: {scores})")
                        print(f"[FALLBACK]     After threshold {fallback_threshold}: {len(above_threshold)} matches (scores: {above_threshold})")
                        
                        all_matches_fallback.extend(image_response.matches)
                    except Exception as e:
                        print(f"[FALLBACK]     ERROR querying image: {e}")
            
            # Sort and filter fallback results
            all_matches_fallback.sort(key=lambda x: x.score, reverse=True)
            
            chunks_fallback = []
            seen_ids_fallback = set()
            for match in all_matches_fallback:
                if match.id not in seen_ids_fallback and match.score >= fallback_threshold:
                    chunks_fallback.append({
                        "id": match.id,
                        "documentId": match.metadata.get("document_id", ""),
                        "score": match.score,
                        "metadata": match.metadata,
                        "content": "",
                        "source_index": match.metadata.get("source_index", "unknown")
                    })
                    seen_ids_fallback.add(match.id)
            
            if chunks_fallback:
                print(f"[FALLBACK] ✅ Found {len(chunks_fallback)} chunks from expanded search!")
                chunks = chunks_fallback  # Replace empty chunks with fallback results
                # Update intent to reflect fallback was used
                intent_result["intent"] = "fallback_all"
                intent_result["original_intent"] = detected_intent
            else:
                print("[FALLBACK] ❌ Even expanded search returned 0 results.")
        
        # If we got results, add the content from the metadata
        if chunks:
            for chunk in chunks:
                # The 'content' is stored in the metadata from Pinecone
                # 'original_text' for text, and 'gcs_url' for image.
                # We can construct a user-friendly content string here.
                md = chunk['metadata']
                source_type = md.get('source')

                # --- FIX: Normalize metadata for different source types ---
                # Ensure 'original_text' is available for the frontend (display & audio)
                if source_type == 'technician_session':
                    if not md.get('original_text'):
                        md['original_text'] = md.get('summary_text', 'Session summary not available.')
                
                elif source_type == 'expert_submission':
                    if not md.get('original_text'):
                        problem = md.get('problem_statement', '')
                        solution = md.get('solution_text', '')
                        md['original_text'] = f"Problem: {problem}\nSolution: {solution}"

                # Now set the chunk['content'] for the summary generator
                if md.get('type') == 'text' or source_type in ['technician_session', 'expert_submission', 'expert_tip']:
                    chunk['content'] = md.get('original_text', 'Text content not available.')
                elif md.get('type') == 'image':
                    # For images, the content is the GCS URL, which can be used by the frontend
                    chunk['content'] = f"Image Source: {md.get('gcs_url', 'Image URL not available.')}"
                else:
                    chunk['content'] = 'Content not available.'
        
        # Log the retrieval action
        try:
            log_retrieval(user_data, request.query, chunks)
        except Exception as log_error:
            print(f"Error logging retrieval: {str(log_error)}")
        
        print(f"[RAG_DEBUG] ==> EXITING retrieve_document_chunks with {len(chunks)} chunks.")
        return chunks[:request.max_results], intent_result

    except Exception as e:
        print(f"[RAG_DEBUG] UNCAUGHT ERROR in retrieve_document_chunks: {str(e)}")
        traceback.print_exc()
        return [], intent_result

# --- Function to log document retrievals for analytics ---
def log_retrieval(user_data: dict, query: str, retrieved_chunks: List[Dict[str, Any]]):
    """
    Log document retrievals for analytics and auditing
    """
    try:
        # Initialize Firestore client
        db_client = get_firestore_client()
        
        # Create a retrieval log document
        retrieval_ref = db_client.collection('retrievalLogs').document()
        
        # Prepare log data
        log_data = {
            'id': retrieval_ref.id,
            'timestamp': SERVER_TIMESTAMP,
            'userId': user_data.get('uid'),
            'userEmail': user_data.get('email'),
            'role': user_data.get('role'),
            'company': user_data.get('company'),
            'organization': user_data.get('organization'),
            'query': query,
            'retrievedChunks': [
                {
                    'chunkId': chunk['id'],
                    'documentId': chunk['documentId'],
                    'score': chunk['score'],
                    'title': chunk['metadata'].get('title', ''),
                    'type': chunk['metadata'].get('type', 'unknown')
                } for chunk in retrieved_chunks
            ]
        }
        
        # Save the log
        retrieval_ref.set(log_data)
        
    except Exception as e:
        print(f"Error logging retrieval: {str(e)}")
        # Don't fail the retrieval process if logging fails
        pass

# --- NEW WEBSOCKET ENDPOINT ---
@router.websocket("/ws/retrieve-knowledge")
async def websocket_retrieve_knowledge(websocket: WebSocket, user: AuthorizedUser):
    await websocket.accept("databutton.app")
    
    try:
        # --- 1. Initial Setup (Get credentials and user data) ---
        await websocket.send_json({"status": "info", "message": "Connection established. Setting up..."})
        
        db_client = get_firestore_client()
        user_ref = db_client.collection('users').document(user.sub)
        user_doc = user_ref.get()
        if not user_doc.exists:
            await websocket.send_json({"status": "error", "message": "User not found."})
            return
        user_data = user_doc.to_dict()

        # --- 2. Receive the query from the client ---
        await websocket.send_json({"status": "info", "message": "Ready to receive your query."})
        data = await websocket.receive_json()
        query = data.get("query")
        if not query:
            await websocket.send_json({"status": "error", "message": "Query not provided."})
            return

        # ✅ ADD: Extract namespaces from frontend
        namespaces = data.get("namespaces")  # Will be ["documents"], ["sessions"], ["expert_tips"], or ["documents", "sessions", "expert_tips"]

        # --- 3. Run the model loading and retrieval in a background task ---
        await websocket.send_json({"status": "processing", "message": "Knowledge base is being initialized. This may take a moment..."})

        # Create a request object for the retrieval function
        retrieval_request_obj = RetrievalRequest(
            query=query,
            company=user_data.get("company"),
            max_results=5,
            score_threshold=0.5,  # UPDATED: Tier 1 Threshold (Intent Specific)
            media_urls=data.get("media_urls"),
            namespaces=namespaces  # ✅ ADD: Pass namespaces to request
        )

        # Use asyncio.to_thread to run our blocking `retrieve_document_chunks` function
        # without blocking the WebSocket's event loop.
        retrieved_chunks, intent_result = await asyncio.to_thread(
            retrieve_document_chunks,
            request=retrieval_request_obj,
            user_data=user_data
        )

        # --- NEW: Fetch and format constraints (before logging) ---
        constraints_text = None
        constraint_stats = {"count": 0, "by_severity": {}, "by_category": {}}
        
        try:
            # Get user company and domain from user_data
            user_company = user_data.get('company')
            # FIX: Use 'assignedDomain' instead of 'domain' as that is where it is stored by user management
            user_domain = user_data.get('assignedDomain')
            
            if user_company and user_domain:
                print(f"[CONSTRAINT] Fetching constraints for company '{user_company}' in domain '{user_domain}'")
                
                # Fetch active constraints (function internally uses company-based filtering)
                active_constraints = await asyncio.to_thread(
                    get_active_constraints,
                    user_id=user.sub,  # Used to get company, but we already have it
                    domain=user_domain
                )
                
                if active_constraints:
                    print(f"[CONSTRAINT] ✅ Found {len(active_constraints)} active constraints for company '{user_company}'")
                    
                    # Format constraints for Gemini
                    constraints_text = format_constraints_for_gemini(active_constraints)
                    
                    # Calculate stats for logging
                    constraint_stats["count"] = len(active_constraints)
                    for constraint in active_constraints:
                        severity = constraint.get('severity', 'unknown')
                        category = constraint.get('category', 'unknown')
                        constraint_stats["by_severity"][severity] = constraint_stats["by_severity"].get(severity, 0) + 1
                        constraint_stats["by_category"][category] = constraint_stats["by_category"].get(category, 0) + 1
                    
                    print(f"[CONSTRAINT] 📊 Stats: {constraint_stats}")
                else:
                    print(f"[CONSTRAINT] ⚠️ No active constraints found for company '{user_company}' in domain '{user_domain}'")
            else:
                if not user_company:
                    print("[CONSTRAINT] ⚠️ User has no company set, skipping constraint fetch")
                if not user_domain:
                    print("[CONSTRAINT] ⚠️ User has no domain set, skipping constraint fetch")
                
        except Exception as e_constraint:
            print(f"[CONSTRAINT] ❌ Failed to fetch/format constraints: {str(e_constraint)}")
            traceback.print_exc()
            # Don't fail the entire search if constraints fail, just continue without them

        # Log the knowledge search to responseLogs collection
        try:
            response_log_ref = db_client.collection('responseLogs').document()
            knowledge_sources = [{
                'chunkId': chunk['id'],
                'documentId': chunk['documentId'],
                'score': chunk['score'],
                'title': chunk['metadata'].get('title', ''),
                'type': chunk['metadata'].get('type', 'unknown')
            } for chunk in retrieved_chunks]
            
            log_data = {
                'id': response_log_ref.id,
                'timestamp': datetime.now(),
                'userId': user.sub,
                'userEmail': user.email,
                'role': user_data.get('role'),
                'company': user_data.get('company'),
                'organization': user_data.get('organization'),
                'query': query,
                'usedRAG': True,
                'knowledgeSources': knowledge_sources,
                'usedWebSearch': False,
                'webSources': [],
                'responseLength': len("summary will be here"),  # Will update after summary generation
                'searchType': 'knowledge_search',  # Mark this as knowledge search
                'constraintsApplied': constraint_stats  # NEW: Add constraint usage statistics
            }
            response_log_ref.set(log_data)
            print(f"[DEBUG] WebSocket knowledge search logged to responseLogs: {len(retrieved_chunks)} chunks retrieved, {constraint_stats['count']} constraints applied")
        except Exception as e_log:
            print(f"[ERROR] Failed to log WebSocket knowledge search: {str(e_log)}")
            # Don't fail the search if logging fails

        # NEW: Get technician's uploaded file content if present
        technician_data = None
        if data.get("media_urls"):
            # Download the file content from GCS
            try:
                gcs_url = data["media_urls"][0]
                if gcs_url.startswith("gs://"):
                    gcs_client = _get_gcs_client()
                    if gcs_client:
                        bucket_name, blob_name = gcs_url.replace("gs://", "").split("/", 1)
                        blob = gcs_client.bucket(bucket_name).blob(blob_name)
                        downloaded_bytes = blob.download_as_bytes()
                        # Try to decode as text, otherwise use as binary representation
                        try:
                            technician_data = downloaded_bytes.decode('utf-8', errors='ignore')
                        except:
                            technician_data = f"Binary file content ({len(downloaded_bytes)} bytes)"
                        print(f"[WEBSOCKET] Downloaded technician file: {len(downloaded_bytes)} bytes")
            except Exception as e:
                print(f"[WEBSOCKET] Could not download technician file: {e}")
                technician_data = None

        await websocket.send_json({"status": "processing", "message": "Synthesizing answer..."})

        # Call the new generator function
        summary = generate_summary(
            query, 
            retrieved_chunks, 
            intent=intent_result["intent"],
            technician_data=technician_data,
            constraints=constraints_text  # Pass formatted constraints
        )

        # --- 4. Send the final result ---
        await websocket.send_json({
            "status": "complete",
            "data": {
                "summary": summary,
                "sources": [chunk["metadata"] for chunk in retrieved_chunks],
                "intent": intent_result["intent"],  # NEW: Let frontend know what intent was detected
                "intent_confidence": intent_result["confidence"]  # NEW
            }
        })

    except WebSocketDisconnect:
        print("Client disconnected from knowledge_retrieval websocket.")
    except Exception as e:
        error_message = f"An error occurred in knowledge_retrieval websocket: {str(e)}"
        print(error_message)
        traceback.print_exc()
        try:
            await websocket.send_json({"status": "error", "message": error_message})
        except RuntimeError:
            pass # Connection likely closed
    finally:
        # --- 5. Cleanup ---
        print("WebSocket connection closed and cleaned up.")


# --- STREAMING KNOWLEDGE WEBSOCKET ENDPOINT ---
@router.websocket("/ws/stream-knowledge")
async def websocket_stream_knowledge(websocket: WebSocket, user: AuthorizedUser):
    await websocket.accept("databutton.app")
    
    try:
        # 1. Initial Setup
        await websocket.send_json({"status": "info", "message": "Stream connection established. Initializing..."})
        
        db_client = get_firestore_client()
        user_ref = db_client.collection('users').document(user.sub)
        user_doc = user_ref.get()
        if not user_doc.exists:
            await websocket.send_json({"status": "error", "message": "User not found."})
            return
        user_data = user_doc.to_dict()

        # 2. Receive Query
        await websocket.send_json({"status": "info", "message": "Ready for query."})
        data = await websocket.receive_json()
        query = data.get("query")
        media_urls = data.get("media_urls")

        if not query:
            await websocket.send_json({"status": "error", "message": "Query cannot be empty."})
            return

        # 3. Retrieve Chunks
        await websocket.send_json({"status": "processing", "message": "Searching knowledge base..."})
        
        retrieval_request_obj = RetrievalRequest(
            query=query,
            company=user_data.get("company"),
            max_results=10,
            score_threshold=0.5, # UPDATED: Tier 1 Threshold (Intent Specific)
            media_urls=media_urls
        )

        retrieved_chunks, intent_result = await asyncio.to_thread(
            retrieve_document_chunks,
            request=retrieval_request_obj,
            user_data=user_data
        )

        # 4. Log the knowledge search to responseLogs collection
        try:
            response_log_ref = db_client.collection('responseLogs').document()
            knowledge_sources = [{
                'id': chunk['id'],
                'documentId': chunk.get('documentId', ''),
                'score': chunk['score'],
                'metadata': chunk.get('metadata', {}),
                'source_index': chunk.get('source_index', 'unknown')
            } for chunk in retrieved_chunks]
            
            log_data = {
                'id': response_log_ref.id,
                'timestamp': datetime.now(),
                'userId': user.sub,
                'userEmail': user.email,
                'role': user_data.get('role'),
                'company': user_data.get('company'),
                'organization': user_data.get('organization'),
                'query': query,
                'usedRAG': True,
                'knowledgeSources': knowledge_sources,
                'usedWebSearch': False,
                'webSources': [],
                'responseLength': 0,  # Knowledge search doesn't generate text response
                'searchType': 'knowledge_search'  # Mark this as a knowledge search vs response generation
            }
            response_log_ref.set(log_data)
            print(f"[DEBUG] WebSocket knowledge search logged to responseLogs: {len(retrieved_chunks)} chunks retrieved")
        except Exception as e_log:
            print(f"[ERROR] Failed to log WebSocket knowledge search: {str(e_log)}")
            # Don't fail the search if logging fails

        # 5. Stream Chunks
        if not retrieved_chunks:
            await websocket.send_json({"status": "info", "message": "No relevant documents found."})
        else:
            await websocket.send_json({"status": "info", "message": f"Found {len(retrieved_chunks)} results. Streaming..."})
            for chunk in retrieved_chunks:
                await websocket.send_json({
                    "status": "chunk",
                    "data": chunk
                })
                await asyncio.sleep(0.05) # Small delay for better UX

        # 6. Completion
        await websocket.send_json({"status": "complete", "message": "Stream finished."})

    except WebSocketDisconnect:
        print("Client disconnected from stream-knowledge websocket.")
    except Exception as e:
        error_message = f"An error occurred in stream-knowledge websocket: {str(e)}"
        print(error_message)
        traceback.print_exc()
        try:
            await websocket.send_json({"status": "error", "message": error_message})
        except RuntimeError:
            pass # Connection likely closed
    finally:
        print("Knowledge stream WebSocket connection closed and cleaned up.")


@router.post("/retrieve-knowledge", response_model=RetrievalResponse)
def retrieve_knowledge(user: AuthorizedUser, request: RetrievalRequest = Body(...)):
    """
    Retrieve relevant document chunks from knowledge base based on query
    """
    try:
        # Get Google Cloud credentials
        db_client = get_firestore_client()
        user_ref = db_client.collection('users').document(user.sub)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
            
        user_data = user_doc.to_dict()
        
        # Check if RAG is enabled in settings
        settings_ref = db_client.collection('settings').document('rag')
        settings_doc = settings_ref.get()
        
        rag_enabled = True  # Default to enabled
        
        if settings_doc.exists:
            settings = settings_doc.to_dict()
            rag_enabled = settings.get('enabled', True)
        
        if not rag_enabled:
            print("RAG is disabled in system settings")
            # If RAG is disabled, return empty results
            return RetrievalResponse(
                chunks=[],
                query=request.query
            )
            
        print(f"RAG is enabled, proceeding with company: {request.company if request.company else user_data.get('company')}")
        
        # Override company filter for system admins
        if user_data.get('role') == 'system_admin' and request.company:
            # Allow system admins to specify a company to filter by
            user_data_for_query = dict(user_data)
            user_data_for_query['company'] = request.company
        else:
            user_data_for_query = user_data
        
        # Retrieve document chunks
        try:
            chunks, intent_result = retrieve_document_chunks(
                request=request,
                user_data=user_data_for_query,
            )
            print(f"Retrieved {len(chunks)} document chunks for query: {request.query}")
            print(f"Detected intent: {intent_result['intent']} (confidence: {intent_result['confidence']})")
        except Exception as e:
            print(f"Error in document retrieval: {str(e)}")
            chunks = []
        
        # Convert to response model
        document_chunks = [
            Chunk(
                id=chunk['id'],
                documentId=chunk['documentId'],
                content=chunk['content'],
                metadata=chunk['metadata'],
                score=chunk['score'],
                source_index=chunk.get('source_index'),
                image_embedding=chunk.get('image_embedding', None),
                text_embedding=chunk.get('text_embedding', None)
            ) for chunk in chunks
        ]
        
        # Log the knowledge search to responseLogs collection
        try:
            response_log_ref = db_client.collection('responseLogs').document()
            knowledge_sources = [{
                'id': chunk['id'],
                'documentId': chunk.get('documentId', ''),
                'score': chunk['score'],
                'metadata': chunk.get('metadata', {}),
                'source_index': chunk.get('source_index', 'unknown')
            } for chunk in chunks]
            
            log_data = {
                'id': response_log_ref.id,
                'timestamp': datetime.now(),
                'userId': user.sub,
                'userEmail': user.email,
                'role': user_data.get('role'),
                'company': user_data.get('company'),
                'organization': user_data.get('organization'),
                'query': request.query,
                'usedRAG': True,
                'knowledgeSources': knowledge_sources,
                'usedWebSearch': False,
                'webSources': [],
                'responseLength': 0,  # Knowledge search doesn't generate text response
                'searchType': 'knowledge_search'  # Mark this as a knowledge search vs response generation
            }
            response_log_ref.set(log_data)
            print(f"[DEBUG] Knowledge search logged to responseLogs: {len(chunks)} chunks retrieved")
        except Exception as e_log:
            print(f"[ERROR] Failed to log knowledge search: {str(e_log)}")
            # Don't fail the search if logging fails
        
        return RetrievalResponse(
            chunks=document_chunks,
            query=request.query
        )
        
    except Exception as e:
        error_message = f"Error retrieving knowledge: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)

@router.get("/company-namespaces", response_model=CompanyNamespacesResponse)
def get_company_namespaces_endpoint(user: AuthorizedUser):
    """
    Get the namespace configuration for the authenticated user's company.
    Returns list of namespaces with their IDs and display names.
    """
    try:
        # Get Firestore client
        db_client = get_firestore_client()
        
        # Get user's company from Firestore
        user_doc = db_client.collection('users').document(user.sub).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = user_doc.to_dict()
        user_company = user_data.get('company')
        
        if not user_company:
            raise HTTPException(status_code=400, detail="User company not found")
        
        # Fetch full namespace configuration from Firestore
        settings_doc = db_client.collection("settings").document(user_company).get()
        default_namespace = get_default_namespace(user_company)
        
        namespaces = []
        if settings_doc.exists:
            settings = settings_doc.to_dict()
            namespace_config = settings.get("namespaceConfiguration", {})
            
            if namespace_config.get("enabled", False):
                custom_namespaces = namespace_config.get("namespaces", [])
                namespaces = [
                    NamespaceInfo(
                        id=ns["id"],
                        displayName=ns.get("displayName", ns["id"]),
                        isDefault=(ns["id"] == default_namespace)
                    )
                    for ns in custom_namespaces
                ]
        
        # Fallback to defaults if no custom namespaces
        if not namespaces:
            from app.libs.namespace_utils import DEFAULT_NAMESPACES
            namespaces = [
                NamespaceInfo(
                    id=ns["id"],
                    displayName=ns["displayName"],
                    isDefault=(ns["id"] == default_namespace)
                )
                for ns in DEFAULT_NAMESPACES
            ]
        
        print(f"[DEBUG] Returning {len(namespaces)} namespaces for company {user_company}")
        for ns in namespaces:
            print(f"[DEBUG]   - {ns.id} (displayName: {ns.displayName}, isDefault: {ns.isDefault})")
        
        return CompanyNamespacesResponse(namespaces=namespaces)
        
    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Error fetching company namespaces: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)
