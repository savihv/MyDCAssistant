from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field
import databutton as db
import pinecone  # type: ignore
from app.auth import AuthorizedUser
from google.cloud.firestore import Client as FirestoreClient  # type: ignore
from google.cloud.storage import Client as StorageClient  # type: ignore
import tempfile
import os
import traceback
from typing import List, Optional
from unstructured.cleaners.core import clean_extra_whitespace  # type: ignore
import app.libs.user_utils as user_utils
import json
from datetime import datetime
import io
from PIL import Image  # type: ignore
import asyncio
from google.cloud import storage as gcs  # type: ignore
import re
from app.libs.firebase_config import get_firestore_client as get_firebase_firestore_client, get_firebase_credentials_dict, get_gcs_credentials, get_gcs_credentials_json
from app.libs.gemini_client import get_gemini_client

router = APIRouter()

# --- Globals and Initial Configuration ---
# These are initialized once when the module is loaded.
try:
    pinecone_api_key = os.environ.get("PINECONE_API_KEY")
    pc = pinecone.Pinecone(api_key=pinecone_api_key)
    
    # The index is no longer connected here. It will be connected dynamically
    # within the endpoint based on the user's company.
    print("Knowledge Base: Pinecone client configured at startup.")
    
except Exception as e:
    # If initial configuration fails, log it. The app might still run if these
    # services are not critical for all endpoints.
    print(f"Knowledge Base: ERROR at startup - Failed to configure clients: {e}")

# --- Pydantic Models ---
class AddSessionRequest(BaseModel):
    sessionId: str
    target_index: Optional[str] = "troubleshooting-sessions"  # ✅ Sessions go to troubleshooting-sessions  namespace


class AddEntryResponse(BaseModel):
    message: str
    pinecone_vector_id: str

class ExpertKnowledgeRequest(BaseModel):
    entryId: str
    problem: str
    solution: str
    tags: List[str]
    target_index: Optional[str] = "expert" 

class DeleteSessionRequest(BaseModel):
    sessionId: str
    target_index: Optional[str] = "troubleshooting-sessions"

class DeleteSessionResponse(BaseModel):
    message: str
    pinecone_vector_id: str

class ExpertTipRequest(BaseModel):
    document_id: str

# --- Helper Functions ---
def get_user_company(uid: str) -> str:
    """Retrieves the company ID for a given user from Firestore."""
    try:
        db_client = get_firebase_firestore_client()
        user_doc = db_client.collection('users').document(uid).get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail=f"User with UID '{uid}' not found.")
        
        user_data = user_doc.to_dict()
        company_id = user_data.get('company')
        if not company_id:
            raise HTTPException(status_code=400, detail=f"User '{uid}' is not associated with a company.")
        return company_id
    except Exception as e:
        print(f"Error retrieving user company for UID {uid}: {e}")
        # Re-raising as HTTPException to ensure client gets a proper error response
        if not isinstance(e, HTTPException):
            raise HTTPException(status_code=500, detail="An internal error occurred while fetching user data.")
        raise e

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError ("Type %s not serializable" % type(obj))

def generate_session_summary(session_data: dict) -> str:
    """Generate a concise summary from the session data for embedding."""
    try:
        model = get_gemini_client()
        prompt = "Summarize the following session for a technical troubleshooting knowledge base. Focus on machine parts, model numbers, error messages on screens, and component conditions. This summary will be used for semantic search."
        # Convert the dictionary to a JSON string for the model, using a custom serializer for datetime objects
        session_text = json.dumps(session_data, indent=2, default=json_serial)
        response = model.generate_content([prompt, session_text], model='gemini-2.5-pro')
        return response
    except Exception as e:
        print(f"Error generating session summary: {e}")
        return ""

# Configure Gemini for Text
generative_model_text = get_gemini_client()

# Configure Gemini for Vision
generative_model_vision = get_gemini_client()

async def describe_image_with_gemini_pro_vision(image_bytes: bytes) -> Optional[str]:
    """Generates a textual description of an image using the latest Gemini model."""
    try:
        # Prepare the text part of the prompt
        prompt_text = "Describe this image for a technical troubleshooting context. Focus on machine parts, model numbers, error messages on screens, and the physical state of components (e.g., 'a frayed wire,' 'a leaking valve,' 'a red indicator light'). Be concise and factual."
        
        # Use the correct generate_with_image method with proper parameter names
        response = await asyncio.to_thread(
            generative_model_vision.generate_with_image,
            text_prompt=prompt_text,
            image_data=image_bytes,
            model="gemini-2.0-flash-exp"
        )
        
        # generate_with_image returns a plain string, not a response object
        return response.strip() if response else None
    except Exception as e:
        print(f"Error describing image with Gemini: {e}")
        return None

async def describe_video_with_gemini_vision(video_bytes: bytes, mime_type: str = "video/mp4") -> Optional[str]:
    """Generates a textual description of a video using Gemini 2.0 Flash.
    
    Args:
        video_bytes: Raw video file bytes
        mime_type: Video MIME type (video/mp4, video/quicktime, etc.)
        
    Returns:
        Description text or None if generation fails
    """
    try:
        # Prepare the prompt for troubleshooting context
        prompt_text = (
            "Analyze this troubleshooting video in detail. Focus on:\n"
            "1. Equipment or machinery shown\n"
            "2. Visible problems, errors, or malfunctions\n"
            "3. Any error messages on screens or indicators\n"
            "4. Physical state of components (leaks, damage, wear)\n"
            "5. Key events or changes that occur\n"
            "6. Approximate timestamps for important observations\n"
            "Be concise and factual. Prioritize technical details relevant to troubleshooting."
        )
        
        # Use the new generate_with_video method with timeout protection
        response = await asyncio.wait_for(
            asyncio.to_thread(
                generative_model_vision.generate_with_video,
                text_prompt=prompt_text,
                video_data=video_bytes,
                mime_type=mime_type,
                model="gemini-2.0-flash-exp",
                fps=1
            ),
            timeout=60.0  # 60 seconds max
        )
        
        return response.strip() if response else None
        
    except asyncio.TimeoutError:
        print("Error describing video with Gemini: Timeout after 60 seconds")
        return None
    except Exception as e:
        print(f"Error describing video with Gemini: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return None

# --- API Endpoints ---
@router.post("/add-session-to-knowledge-base", status_code=201, tags=["knowledge_base"])
async def add_session_to_knowledge_base(
    request: AddSessionRequest,
    user: AuthorizedUser
):
    """Adds a specific user session's Q&A to the knowledge base."""
    print(f"🚀 Starting 'add_session_to_knowledge_base' for session ID: {request.sessionId}")
    try:
        # --- 1. Setup and Authorization ---
        print("   [1/7] Authorizing user...")
        db_client = get_firebase_firestore_client()
        user_ref = db_client.collection('users').document(user.sub)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = user_doc.to_dict()
        print("      --- [DEBUG] User data fetched successfully.")

        company_id = user_data.get('company')
        print(f"   - User {user.sub} belongs to company: {company_id}")

        if not user_utils.verify_admin_role(user_data) or not company_id:
            print(f"   ❌ Authorization failed for user {user.sub}.")
            raise HTTPException(status_code=403, detail="Unauthorized or user not associated with a company.")
        print("   - ✅ User authorized as admin.")

        # --- 2. Retrieve Session from Firestore ---
        print("   [2/7] Fetching session from Firestore collection 'troubleshootingSessions'...")
        
        session_ref = db_client.collection('troubleshootingSessions').document(request.sessionId)
        session_doc = session_ref.get()
        if not session_doc.exists:
            print(f"   ❌ Session document '{request.sessionId}' not found in 'troubleshootingSessions'.")
            raise HTTPException(status_code=404, detail="Session not found.")
        session_data = session_doc.to_dict()
        print("   - ✅ Session document found.")
        # ✅ FIX: Read target_index from session document
        target_index = session_data.get("target_index", request.target_index or "troubleshooting-sessions")
        print(f" add_session_to_knowledge_base  - Target index from session: {target_index}")

        # --- 3. Generate Summary ---
        print("   [3/7] Generating session summary with Gemini...")
        summary = generate_session_summary(session_data)
        if not summary:
            print("   ❌ Failed to generate session summary.")
            raise HTTPException(status_code=500, detail="Failed to generate session summary.")
        print(f"   - ✅ Summary generated (snippet: {summary[:100]}...)")

        # --- 4. Generate Embedding ---
        print("   [4/7] Generating embedding for the summary...")
        embedding = get_gemini_client().embed_text(
            text=summary,
            model="text-embedding-004",
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768
        )
        print(f"   - ✅ Embedding generated (vector dimension: {len(embedding)}).")

        # --- 5. Upsert to Pinecone ---
        sanitized_company_id = company_id.lower().replace('_', '-')
        sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index).lower()
        index_name = f"techtalk-text-{sanitized_company_id}"
        namespace = f"{sanitized_company_id}-{sanitized_target_index}"
        print(f" add_session_to_knowledge_base  - Target namespace from session: {namespace}")
        
        
        # Create index if it doesn't exist
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        if index_name not in existing_indexes:
            print(f"[SESSION_KB] Creating Pinecone index: {index_name}")
            from pinecone import ServerlessSpec
            pc.create_index(
                name=index_name,
                dimension=768,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
            
        vector_id = f"session-kb-{request.sessionId}"
        print("   [5/7] Preparing to upsert vector to Pinecone:")
        print(f"   - Index: '{index_name}'")
        print(f"   - Namespace: '{namespace}'")
        print(f"   - Vector ID: '{vector_id}'")
        
        metadata = {
            "source": "technician_session",
            "original_session_id": request.sessionId,
            "summary_text": summary,
            "company": company_id,
        }
        
        pinecone_index = pc.Index(index_name)
        print(f"   - Upserting: namespace='{namespace}', vector_id='{vector_id}'")
        upsert_response = pinecone_index.upsert(vectors=[(vector_id, embedding, metadata)], namespace=namespace)
        print(f"   - ✅ Vector upserted to Pinecone successfully. Response: {upsert_response}")

        # --- 5b. Process and Upsert Media (Images AND Videos) from the Session ---
        # Wrap in try-except to ensure Firestore update happens even if media processing fails
        try:
            print("   [5b/7] Processing media files (images and videos) from the session...")
            media_vectors_to_upsert = []
            gcs_paths = session_data.get("mediaGcsPaths", [])

            if not gcs_paths:
                print("   - No media files found in the session's mediaGcsPaths. Skipping media processing.")
            else:
                # --- Initialize GCS Client for secure download ---
                print("   - Initializing GCS client for secure media download...")
                creds = get_gcs_credentials()
                storage_client = StorageClient(credentials=creds)
                print("   - GCS client initialized successfully.")
                
                # Import media type detection helper
                from app.libs.gemini_client import get_media_type_and_mime
                
                print(f"   - Found {len(gcs_paths)} media file(s) to process.")
                for idx, gcs_path in enumerate(gcs_paths):
                    try:
                        # Detect media type
                        media_type, mime_type = get_media_type_and_mime(gcs_path)
                        
                        if media_type == 'unknown':
                            print(f"     - ⚠️ Skipping unsupported file type: {gcs_path}")
                            continue
                        
                        print(f"     - Processing {media_type} {idx + 1}/{len(gcs_paths)} from GCS path: {gcs_path}")

                        # --- Securely download media using authenticated GCS client ---
                        bucket_name, blob_name = gcs_path.replace("gs://", "").split("/", 1)
                        bucket = storage_client.bucket(bucket_name)
                        blob = bucket.blob(blob_name)
                        
                        print(f"       - Downloading blob '{blob_name}' from bucket '{bucket_name}'...")
                        media_bytes = await asyncio.to_thread(blob.download_as_bytes)
                        media_size_mb = len(media_bytes) / (1024 * 1024)
                        print(f"       - Media downloaded successfully ({media_size_mb:.2f}MB).")

                        # --- Generate description based on media type ---
                        description = None
                        
                        if media_type == 'image':
                            # Use existing image description function
                            description = await describe_image_with_gemini_pro_vision(media_bytes)
                            if not description:
                                print(f"       - ❌ Skipping image {idx + 1} due to description generation failure.")
                                continue
                            print(f"       - ✅ Image described (snippet: {description[:80]}...)")
                        
                        elif media_type == 'video':
                            # NEW: Use video description function
                            description = await describe_video_with_gemini_vision(media_bytes, mime_type)
                            if not description:
                                print(f"       - ❌ Skipping video {idx + 1} due to description generation failure.")
                                continue
                            print(f"       - ✅ Video described (snippet: {description[:80]}...)")

                        # Generate embedding for the description
                        embedding = get_gemini_client().embed_text(
                            text=description,
                            model="text-embedding-004",
                            task_type="RETRIEVAL_DOCUMENT",
                            output_dimensionality=768
                        )
                        
                        print("       - ✅ Embedding generated for media description.")
                        
                        # Prepare vector and metadata for Pinecone
                        vector_id = f"session-{media_type}-{request.sessionId}-{idx}"
                        metadata = {
                            "source": f"technician_{media_type}",
                            "media_type": media_type,
                            "original_session_id": request.sessionId,
                            "original_gcs_path": gcs_path,
                            "media_description": description,
                            "company": company_id,
                        }
                        media_vectors_to_upsert.append((vector_id, embedding, metadata))

                    except Exception as media_exc:
                        print(f"   - ❌ Failed to process media file {idx + 1} at {gcs_path}. Error: {media_exc}")
                        print(f"   - Traceback: {traceback.format_exc()}")
                        continue
                
                # Upsert all collected media vectors in one batch
                if media_vectors_to_upsert:
                    print(f"   - Upserting {len(media_vectors_to_upsert)} media vectors to namespace: '{namespace}'")
                    media_upsert_response = pinecone_index.upsert(vectors=media_vectors_to_upsert, namespace=namespace)
                    print(f"   - ✅ All media vectors upserted to Pinecone successfully. Response: {media_upsert_response}")

        except Exception as media_processing_exc:
            print(f"   - ⚠️ Non-critical error during media processing: {media_processing_exc}")
            print("   - Continuing with session update despite media processing errors.")

        # --- 6. Update Session Status in Firestore ---
        print(f"   [6/7] Updating session document '{request.sessionId}' in Firestore...")
        session_ref.update({"is_in_knowledge_base": True})
        print("   - ✅ Firestore document updated with 'is_in_knowledge_base: True'.")

        # --- 7. Final Response ---
        print("   [7/7] ✅ Process complete. Returning success response.")
        return AddEntryResponse(message="Session successfully added to the knowledge base.", pinecone_vector_id=vector_id)

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions to send them directly to the client
        raise http_exc
    except Exception as e:
        print(f"   ❌ An unexpected error occurred: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
            
@router.post("/add-expert-entry-to-knowledge-base", response_model=AddEntryResponse)
async def add_expert_entry_to_knowledge_base(request: ExpertKnowledgeRequest, user: AuthorizedUser):
    try:
        # 1. Determine the correct Pinecone Index
        company_id = get_user_company(user.sub)
        sanitized_company_id = company_id.lower().replace('_', '-')
        sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', request.target_index or 'expert').lower()
        index_name = f"techtalk-text-{sanitized_company_id}"
        namespace = f"{sanitized_company_id}-{sanitized_target_index}"
        print(f" add_expert_entry_to_knowledge_base  - Target namespace from session: {namespace}")
        
        # 2. Create index if it doesn't exist
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        if index_name not in existing_indexes:
            print(f"[EXPERT_ENTRY] Creating Pinecone index: {index_name}")
            from pinecone import ServerlessSpec
            pc.create_index(
                name=index_name,
                dimension=768,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
        
        pinecone_index = pc.Index(index_name)
        
        # 3. Generate a combined text for embedding
        combined_text = f"Problem: {request.problem}\nSolution: {request.solution}"
        
        # 4. Generate Embedding
        embedding = get_gemini_client().embed_text(
            text=combined_text,
            model="text-embedding-004",
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=768
        )
        
        # 5. Prepare and Upsert Data to Pinecone
        vector_id = f"expert-kb-{request.entryId}"
        metadata = {
            "source": "expert_submission",
            "problem_statement": request.problem,
            "solution_text": request.solution,
            "tags": request.tags,
            "company": company_id,
        }
        
        pinecone_index.upsert(vectors=[(vector_id, embedding, metadata)], namespace=namespace)
        
        return AddEntryResponse(message="Expert knowledge entry successfully added.", pinecone_vector_id=vector_id)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.delete("/delete-session-from-knowledge-base", response_model=DeleteSessionResponse)
async def delete_session_from_knowledge_base(
    request: DeleteSessionRequest, user: AuthorizedUser
):
    """Deletes a session's vector from Pinecone and updates Firestore."""
    try:
        # 1. Authorize User and Get Company Info
        print(f"🚀 Starting 'delete_session_from_knowledge_base' for session: {request.sessionId}")
        db_client = get_firebase_firestore_client()
        user_ref = db_client.collection('users').document(user.sub)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=404, detail="User not found")
        user_data = user_doc.to_dict()
        company_id = user_data.get('company')

        if not user_utils.verify_admin_role(user_data) or not company_id:
            raise HTTPException(status_code=403, detail="Unauthorized or user not associated with a company.")
        print(f"   - User {user.sub} from company {company_id} authorized.")

        # 2. Connect to Pinecone and Fetch Session Data
        print("   - Connecting to Pinecone and Firestore...")
        #sanitized_company_id = company_id.lower().replace('_', '-')
        #sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', request.target_index or 'expert').lower()
        #index_name = f"techtalk-text-{sanitized_company_id}"
        #namespace = f"{sanitized_company_id}-{sanitized_target_index}"
        
        # We need to fetch the session to know how many images were processed
        session_ref = db_client.collection('troubleshootingSessions').document(request.sessionId)
        session_doc = session_ref.get()
        if not session_doc.exists:
            # If the session doesn't exist in Firestore, we can't know about the images,
            # but we can still try to delete the main vector.
            print(f"   - Warning: Session document '{request.sessionId}' not found in Firestore. Will only attempt to delete the main summary vector.")
            session_data = {}
            target_index = request.target_index or "troubleshooting-sessions"
            print(f"  delete_session_from_knowledge_base - Using default target_index: {target_index}")
        else:
            session_data = session_doc.to_dict()
            print("   - ✅ Session document found.")
            target_index = session_data.get("target_index", request.target_index or "troubleshooting-sessions")
            print(f" delete_session_from_knowledge_base  - Target index from session: {target_index}")


        # --- Prepare list of all vectors to delete ---
        vectors_to_delete = []

        # Add the main session summary vector
        main_vector_id = f"session-kb-{request.sessionId}"
        vectors_to_delete.append(main_vector_id)
        print(f"   - Queued for deletion: Main summary vector '{main_vector_id}'")

        # Add all associated image description vectors
        image_paths = session_data.get("mediaGcsPaths", [])
        if image_paths:
            print(f"   - Found {len(image_paths)} associated image(s). Queuing their vectors for deletion.")
            for idx in range(len(image_paths)):
                # The vector ID format uses idx, which is 0-based
                img_vector_id = f"session-img-{request.sessionId}-{idx}"
                vectors_to_delete.append(img_vector_id)
                print(f"   - Queued for deletion: Image vector '{img_vector_id}'")
        
        # --- Prepare Deletion ---
        sanitized_company_id = company_id.lower().replace('_', '-')
        sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index).lower()
        index_name = f"techtalk-text-{sanitized_company_id}"
        namespace = f"{sanitized_company_id}-{sanitized_target_index}"
        
        print(f" delete_session_from_knowledge_base  - Target Pinecone index: '{index_name}'")
        print(f" delete_session_from_knowledge_base  - Target namespace: '{namespace}'")
        
        pinecone_index = pc.Index(index_name)
        
        # --- Execute deletion from Pinecone ---
        if not vectors_to_delete:
            print("   - No vectors to delete.")
        else:
            print(f"   - Preparing to delete {len(vectors_to_delete)} vector(s) from index '{index_name}'.")
            try:
                delete_response = pinecone_index.delete(ids=vectors_to_delete, namespace=namespace)
                print(f"   - ✅ Delete command issued to Pinecone for {len(vectors_to_delete)} vector(s). Response: {delete_response}")
            except Exception as pinecone_error:
                error_str = str(pinecone_error).lower()
                # Check if this is a namespace not found error
                if "404" in str(pinecone_error) or "not found" in error_str or "namespace" in error_str:
                    print(f"   - ❌ Namespace '{namespace}' not found in Pinecone index '{index_name}'")
                    raise HTTPException(
                        status_code=404,
                        detail=f"Namespace '{namespace}' not found in Pinecone. Cannot verify deletion. The session may never have been added to the knowledge base, or the namespace structure has changed."
                    )
                else:
                     # Re-raise other Pinecone errors
                     raise

        # 3. Update Firestore
        print(f"   - Updating Firestore document '{request.sessionId}'.")
        # Ensure session_ref is valid even if the doc didn't exist initially
        if session_doc.exists:
            session_ref.update({"is_in_knowledge_base": False})
            print("   - ✅ Firestore document updated with 'is_in_knowledge_base: False'.")
        else:
            print("   - Skipping Firestore update as document was not found.")
        
        # 4. Return Success
        print("   - ✅ Process complete.")
        return DeleteSessionResponse(
            message="Session successfully removed from the knowledge base.",
            pinecone_vector_id=main_vector_id # Return the main vector ID for reference
        )

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"   ❌ An unexpected error occurred: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An unexpected error occurred while deleting the session.")

# --- New Expert Tip Management Endpoints ---

@router.post("/approve_expert_tip", tags=["knowledge_base", "expert_tips"])
async def approve_expert_tip(request: ExpertTipRequest, user: AuthorizedUser):
    """
    Approves an expert tip, processes its content and media, generates an embedding,
    and adds it to the company's Pinecone knowledge base.
    """
    company_id = get_user_company(user.sub)
    db_client = get_firebase_firestore_client()
    creds = get_gcs_credentials()
    storage_client = StorageClient(credentials=creds)
    
    # 1. Fetch the expert tip from Firestore
    doc_ref = db_client.collection("expert_tips").document(request.document_id)
    tip_doc = doc_ref.get()
    
    if not tip_doc.exists:
        raise HTTPException(status_code=404, detail="Expert tip not found.")
    tip_data = tip_doc.to_dict()

    target_index = tip_data.get("target_index", "expert")  # Default to "expert" if not found
    sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index).lower()
    print(f"[EXPERT_TIP_APPROVAL] Processing tip for target_index: {target_index}")

    # 2. Process media files for additional context
    additional_context = []
    media_urls = tip_data.get("mediaUrls", [])
    if media_urls:
        for url in media_urls:
            try:
                # Assuming URLs are in GCS format like 'gs://bucket-name/path/to/file'
                bucket_name, blob_name = url.replace("gs://", "").split("/", 1)
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                file_bytes = await asyncio.to_thread(blob.download_as_bytes)

                if any(ext in url.lower() for ext in ['.png', '.jpeg', '.jpg']):
                    description = await describe_image_with_gemini_pro_vision(file_bytes)
                    if description:
                        additional_context.append(f"Image Analysis: {description}")
                # Placeholder for audio processing if needed in the future
                # elif any(ext in url.lower() for ext in ['.mp3', '.wav']):
                #     transcript = await get_audio_transcript(file_bytes)
                #     additional_context.append(f"Audio Transcript: {transcript}")
            except Exception as e:
                print(f"Failed to process media file {url}: {e}")
    
    # 3. Combine all text for embedding
    combined_text = tip_data.get("description", "")
    if additional_context:
        combined_text += "\n\n--- Media Analysis ---\n" + "\n".join(additional_context)
    
    # 4. Generate embedding and upsert to Pinecone
    sanitized_company_id = company_id.lower().replace('_', '-')
    text_index_name = f"techtalk-text-{sanitized_company_id}"
    # namespace = f"{sanitized_company_id}-{sanitized_target_index}"
    
    # Create index if it doesn't exist
    existing_indexes = pc.list_indexes()
    existing_index_names = [index.name for index in existing_indexes]
    
    if text_index_name not in existing_index_names:
        print(f"[EXPERT_TIP_APPROVAL] Creating Pinecone index: {text_index_name}")
        try:
            from pinecone import ServerlessSpec
            pc.create_index(
                name=text_index_name,
                dimension=768,  # text-embedding-004 dimension
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1")
            )
            print(f"[EXPERT_TIP_APPROVAL] Successfully created index: {text_index_name}")
        except Exception as e:
            if "already exists" not in str(e):
                raise HTTPException(status_code=500, detail=f"Failed to create Pinecone index: {e}")
    
    pinecone_index = pc.Index(text_index_name)
    print(f"[EXPERT_TIP_APPROVAL] >>> Generating embedding for {len(combined_text)} chars")
    embedding = get_gemini_client().embed_text(
        text=combined_text,
        model="text-embedding-004",
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=768
    )
    print(f"[EXPERT_TIP_APPROVAL] ✅ Embedding generated successfully, dimension={len(embedding)}")
    
    metadata = {
        "source_type": "expert_tip",
        "title": tip_data.get("title", ""),
        "original_text": tip_data.get("description", ""),
        "media_urls": ", ".join(media_urls),
        "companyId": company_id,
        "target_index": target_index
    }
    
    pinecone_namespace = f"{sanitized_company_id}-{sanitized_target_index}"
    print(f"[EXPERT_TIP_APPROVAL] Upserting to Pinecone: index={text_index_name}, namespace={pinecone_namespace}, vector_id={request.document_id}")
    upsert_response = pinecone_index.upsert(
        vectors=[(request.document_id, embedding, metadata)], 
        namespace=pinecone_namespace
    )
    print(f"[EXPERT_TIP_APPROVAL] ✅ Pinecone upsert completed: {upsert_response}")
    
    # 5. Update status AND isAddedToKnowledgeBase in Firestore
    doc_ref.update({
        "status": "approved", 
        "processed_text": combined_text,
        "isAddedToKnowledgeBase": True
    })
    
    print(f"[EXPERT_TIP_APPROVAL] Successfully approved and added to knowledge base: {request.document_id}")
    
    return {"message": "Expert tip approved and added to knowledge base."}


@router.post("/reject_expert_tip", tags=["knowledge_base", "expert_tips"])
async def reject_expert_tip(request: ExpertTipRequest, user: AuthorizedUser):
    """
    Rejects an expert tip. If it was previously approved and added to the knowledge base,
    removes it from Pinecone before updating the status to 'rejected'.
    """
    company_id = get_user_company(user.sub)  # Authorize user
    db_client = get_firebase_firestore_client()
    doc_ref = db_client.collection("expert_tips").document(request.document_id)
    
    # Fetch the tip to check if it's in the knowledge base
    tip_doc = doc_ref.get()
    
    if not tip_doc.exists:
        raise HTTPException(status_code=404, detail="Expert tip not found.")
    
    tip_data = tip_doc.to_dict()
    is_in_kb = tip_data.get("isAddedToKnowledgeBase", False)
    
    # If the tip was added to knowledge base, remove it from Pinecone first
    if is_in_kb:
        try:
            target_index = tip_data.get("target_index", "expert")
            sanitized_company_id = company_id.lower().replace('_', '-')
            sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index).lower()
            text_index_name = f"techtalk-text-{sanitized_company_id}"
            namespace = f"{sanitized_company_id}-{sanitized_target_index}"
            
            # Delete from Pinecone if the index exists
            if text_index_name in pc.list_indexes().names():
                pinecone_index = pc.Index(text_index_name)
                pinecone_index.delete(ids=[request.document_id], namespace=namespace)
                print(f"[EXPERT_TIP_REJECT] Deleted vector from Pinecone: {request.document_id}")
            else:
                print(f"[EXPERT_TIP_REJECT] Index '{text_index_name}' not found. Vector may already be deleted.")
        except Exception as e:
            print(f"[EXPERT_TIP_REJECT] Error removing from Pinecone: {e}")
            # Continue with rejection even if Pinecone deletion fails
    
    # Update Firestore with rejected status and reset knowledge base flag
    doc_ref.update({
        "status": "rejected",
        "isAddedToKnowledgeBase": False
    })
    
    return {"message": "Expert tip has been rejected and removed from knowledge base if applicable."}


@router.post("/delete_expert_tip_from_knowledge_base", tags=["knowledge_base", "expert_tips"])
async def delete_expert_tip_from_knowledge_base(request: ExpertTipRequest, user: AuthorizedUser):
    """
    Deletes an approved expert tip from the Pinecone knowledge base and updates
    its status in Firestore to 'deleted'.
    """
    company_id = get_user_company(user.sub)
    db_client = get_firebase_firestore_client()
    doc_ref = db_client.collection("expert_tips").document(request.document_id)

    tip_doc = doc_ref.get()
    
    if not tip_doc.exists:
        raise HTTPException(status_code=404, detail="Expert tip not found.")
    
    tip_data = tip_doc.to_dict()
    target_index = tip_data.get("target_index", "expert")
    sanitized_target_index = re.sub(r'[^a-zA-Z0-9-]', '', target_index).lower()
    
    # Step 1: Delete from Pinecone
    sanitized_company_id = company_id.lower().replace('_', '-')
    text_index_name = f"techtalk-text-{sanitized_company_id}"
    namespace = f"{sanitized_company_id}-{sanitized_target_index}"
    
    if text_index_name in pc.list_indexes().names():
        try:
            pinecone_index = pc.Index(text_index_name)
            pinecone_namespace = namespace
            pinecone_index.delete(ids=[request.document_id], namespace=pinecone_namespace)
            print(f"[EXPERT_TIP_DELETE] Deleted vector from Pinecone: {request.document_id}")
        except Exception as e:
            print(f"Could not delete vector {request.document_id} from Pinecone: {e}")
            # Do not re-raise, still attempt to update Firestore

    # Step 2: Update status AND isAddedToKnowledgeBase in Firestore
    doc_ref.update({
        "status": "deleted",
        "isAddedToKnowledgeBase": False
    })

    return {"message": "Expert tip removed from knowledge base."}
