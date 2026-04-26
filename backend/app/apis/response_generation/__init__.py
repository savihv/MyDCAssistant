from fastapi import APIRouter, HTTPException, Body, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import databutton as db
import os
from datetime import datetime
import json
import time
import asyncio
from google.cloud import texttospeech, storage  # type: ignore
import base64
import re
import traceback
import mimetypes
from io import BytesIO

from google.cloud.firestore import SERVER_TIMESTAMP  # type: ignore
from app.libs.firebase_config import get_firestore_client, get_firebase_credentials_dict
from google.oauth2 import service_account  # type: ignore

from app.env import mode, Mode

from app.apis.knowledge_retrieval import retrieve_knowledge, RetrievalRequest
from app.apis.web_search import search_web, WebSearchRequest, WebSearchResponse, WebSearchResult
from app.libs.constraint_manager import get_active_constraints, format_constraints_for_gemini
from app.auth import AuthorizedUser
from app.libs.auth_helpers import verify_internal_worker_request
from app.libs.gemini_client import get_gemini_client

router = APIRouter()


# --- 1. NEW HELPER FUNCTION: Text Splitter ---
# Max bytes for synchronous TTS is typically 5000, we use a buffer.
MAX_CHUNK_SIZE_BYTES = 4500


# --- NEW: Async TTS Processor ---
async def process_tts_async(
    session_id: str,
    command_id: str,
    text: str,
    tts_client: texttospeech.TextToSpeechClient,
    timeout_per_chunk: int = 30  # 30 seconds per chunk max
):
    """Process TTS in background and update Firestore when ready"""
    firestore_client = None
    try:
        print(f"[TTS_ASYNC] Starting background TTS for session {session_id}")
        firestore_client = get_firestore_client()
        
        # Validate text length
        text_bytes = len(text.encode('utf-8'))
        print(f"[TTS_ASYNC] Text size: {text_bytes} bytes")
        
        if text_bytes > 100000:  # ~100KB is extremely long
            raise ValueError(f"Text too long for TTS: {text_bytes} bytes")
        
        # Split text and process TTS
        text_chunks = split_text_by_size(text)
        print(f"[TTS_ASYNC] Processing {len(text_chunks)} chunks")
        
        full_audio = None
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="en-US", 
            name="en-US-Studio-O"
        )
        audio_config_params = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        for i, chunk in enumerate(text_chunks):
            try:
                # Validate chunk size
                chunk_bytes = len(chunk.encode('utf-8'))
                if chunk_bytes > MAX_CHUNK_SIZE_BYTES:
                    print(f"[TTS_ASYNC] ⚠️ WARNING: Chunk {i+1} exceeds limit: {chunk_bytes} bytes")
                    # Truncate if still too large
                    chunk = chunk[:4000]
                
                synthesis_input = texttospeech.SynthesisInput(text=chunk)
                print(f"[TTS_ASYNC] Synthesizing chunk {i+1}/{len(text_chunks)}. Size: {chunk_bytes} bytes.")
                
                # Add timeout wrapper for individual TTS call
                import asyncio
                tts_api_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        tts_client.synthesize_speech,
                        input=synthesis_input,
                        voice=voice_params,
                        audio_config=audio_config_params
                    ),
                    timeout=timeout_per_chunk
                )
                
                # Collect MP3 bytes directly instead of using AudioSegment
                if full_audio is None:
                    full_audio = bytearray(tts_api_response.audio_content)
                else:
                    # Note: Simple MP3 concatenation (no silence padding)
                    # For proper silence, would need MP3 manipulation library
                    full_audio.extend(tts_api_response.audio_content)
                    
                print(f"[TTS_ASYNC] ✅ Chunk {i+1}/{len(text_chunks)} completed")
                
            except asyncio.TimeoutError:
                error_msg = f"TTS timeout on chunk {i+1}/{len(text_chunks)}"
                print(f"[TTS_ASYNC] ⏱️ {error_msg}")
                raise TimeoutError(error_msg)
            except Exception as e_chunk:
                error_msg = f"TTS failed on chunk {i+1}/{len(text_chunks)}: {str(e_chunk)}"
                print(f"[TTS_ASYNC] ❌ {error_msg}")
                raise Exception(error_msg)
        
        # Save audio
        if full_audio:
            print("[TTS_ASYNC] Exporting combined audio...")
            final_audio_content = bytes(full_audio)
            
            audio_filename = sanitize_storage_key(
                f"audio_{session_id}_{command_id}.mp3"
            )
            db.storage.binary.put(key=audio_filename, value=final_audio_content)
            
            # Build audio URL
            if mode == Mode.PROD:
                base_url = "https://riff.new/_projects/24943f2a-846d-4587-b501-f26cc2851ea5/dbtn/prodx/app/routes"
            else:
                base_url = "https://riff.new/_projects/24943f2a-846d-4587-b501-f26cc2851ea5/dbtn/devx/app/routes"
            
            audio_url = f"{base_url}/audio_files/stream/{audio_filename}"
            
            # Update Firestore with audio URL
            command_ref = firestore_client.collection('troubleshootingSessions').document(session_id).collection('voiceCommands').document(command_id)
            
            command_ref.update({
                'responseAudioUrl': audio_url,
                'audioProcessedTimestamp': SERVER_TIMESTAMP,
                'audioProcessingError': None  # Clear any previous errors
            })
            
            # Also update session document
            session_ref = firestore_client.collection('troubleshootingSessions').document(session_id)
            session_ref.update({
                'responseAudioUrl': audio_url,
                'status': 'awaiting_feedback',
                'audioProcessingError': None  # Clear any previous errors
            })
            
            print(f"[TTS_ASYNC] ✅ Audio ready and Firestore updated: {audio_url}")
        else:
            raise Exception("No audio generated - full_audio is None")
            
    except Exception as e:
        error_message = f"TTS processing failed: {str(e)}"
        print(f"[TTS_ASYNC] ❌ {error_message}")
        print(f"[TTS_ASYNC] Traceback:\n{traceback.format_exc()}")
        
        # Update Firestore with error status so frontend knows
        try:
            if not firestore_client:
                firestore_client = get_firestore_client()
                
            command_ref = firestore_client.collection('troubleshootingSessions').document(session_id).collection('voiceCommands').document(command_id)
            command_ref.update({
                'audioProcessingError': error_message,
                'audioProcessedTimestamp': SERVER_TIMESTAMP
            })
            
            session_ref = firestore_client.collection('troubleshootingSessions').document(session_id)
            session_ref.update({
                'status': 'audio_failed',
                'audioProcessingError': error_message
            })
            
            print("[TTS_ASYNC] Error status saved to Firestore")
        except Exception as e_firestore:
            print(f"[TTS_ASYNC] Failed to save error to Firestore: {str(e_firestore)}")


# --- Pydantic Models ---
# Force regeneration 2024-07-19
class ChatMessage(BaseModel):
    role: str = Field(..., description="The role of the message sender ('user' or 'assistant')")
    content: str = Field(..., description="The content of the message")

class ResponseRequest(BaseModel):
    session_id: str = Field(..., description="The ID of the troubleshooting session")
    transcript: str = Field(..., description="The transcribed voice command")
    uid: str = Field(..., description="The ID of the user requesting the response")
    command_id: str = Field(..., description="The ID of the user's command document in Firestore")
    history: Optional[List[ChatMessage]] = Field(None, description="The conversation history")
    media_urls: Optional[List[str]] = Field(None, description="GCS URLs of any media files")
    session_organization: Optional[str] = Field(None, description="Organization from the current session")
    use_knowledge_base: Optional[bool] = Field(True, description="Whether to use the knowledge base for RAG")
    use_web_search: Optional[bool] = Field(True, description="Whether to use web search")

class ResponseData(BaseModel):
    text_response: str = Field(..., description="The AI-generated text response")
    audio_url: Optional[str] = Field(None, description="URL to the generated audio response")
    user_has_submitted_feedback: bool = Field(False, description="Indicates if user submitted feedback for this session")
    status: str = Field("success", description="Overall status of the response generation")
    notes: Optional[str] = Field(None, description="Additional notes or error details")
    knowledge_sources_used: Optional[List[Dict[str, Any]]] = Field(None, description="Knowledge base sources used")
    web_sources_used: Optional[List[Dict[str, Any]]] = Field(None, description="Web sources used")


def sanitize_storage_key(key: str) -> str:
    """Sanitize storage key to only allow alphanumeric and ._- symbols"""
    return re.sub(r'[^a-zA-Z0-9._-]', '', key)

def split_text_by_size(text: str) -> list[str]:
    """
    Splits text into chunks under MAX_CHUNK_SIZE_BYTES, prioritizing sentence endings.
    Enhanced to handle edge cases and ensure no chunk exceeds the limit.
    """
    if len(text.encode('utf-8')) <= MAX_CHUNK_SIZE_BYTES:
        return [text]

    # Split on sentence boundaries (., !, ?)
    sentences = re.split(r'([.!?]+\s+)', text)
    
    # Rejoin sentences with their punctuation
    rejoined_sentences = []
    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        if i + 1 < len(sentences):
            sentence += sentences[i+1]
        if sentence.strip():
            rejoined_sentences.append(sentence.strip())

    chunks = []
    current_chunk = ""

    for sentence in rejoined_sentences:
        sentence_bytes = len(sentence.encode('utf-8'))
        
        # If a single sentence is too large, split it by words
        if sentence_bytes > MAX_CHUNK_SIZE_BYTES:
            words = sentence.split()
            temp_chunk = ""
            for word in words:
                test_chunk = temp_chunk + (" " if temp_chunk else "") + word
                if len(test_chunk.encode('utf-8')) > MAX_CHUNK_SIZE_BYTES:
                    if temp_chunk:
                        chunks.append(temp_chunk)
                    temp_chunk = word
                else:
                    temp_chunk = test_chunk
            if temp_chunk:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                chunks.append(temp_chunk)
            continue
        
        # Try adding sentence to current chunk
        test_chunk = current_chunk + (" " if current_chunk else "") + sentence
        
        if len(test_chunk.encode('utf-8')) > MAX_CHUNK_SIZE_BYTES:
            # Current chunk is full, save it and start new one
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
        else:
            current_chunk = test_chunk
    
    # Add remaining chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    # Fallback: if no chunks created, force split
    if not chunks:
        chunks = [text]
    
    print(f"[TTS_DEBUG] Split text into {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"[TTS_DEBUG] Chunk {i+1} size: {len(chunk.encode('utf-8'))} bytes")
    
    return chunks
    
async def log_response_generation(user_data: dict, query: str, used_rag: bool, knowledge_sources: list, used_web_search: bool = False, web_sources: Optional[list] = None, response_text: str = "", constraint_stats: Optional[Dict[str, Any]] = None):
    print("[DEBUG] log_response_generation: Entered function.")
    if web_sources is None:
        web_sources = []
    try:
        db_client = get_firestore_client()
        print("[DEBUG] log_response_generation: Firestore client initialized.")
        
        response_log_ref = db_client.collection('responseLogs').document()
        log_data = {
            'id': response_log_ref.id,
            'timestamp': datetime.now(),
            'userId': user_data.get('uid'),
            'userEmail': user_data.get('email'),
            'role': user_data.get('role'),
            'company': user_data.get('company'),
            'organization': user_data.get('organization'),
            'query': query,
            'usedRAG': used_rag,
            'knowledgeSources': knowledge_sources,
            'usedWebSearch': used_web_search,
            'webSources': web_sources,
            'responseLength': len(response_text),
            'constraintsApplied': constraint_stats
        }
        response_log_ref.set(log_data)
        print("[DEBUG] log_response_generation: Log data set successfully.")
    except Exception as e:
        print(f"[ERROR] log_response_generation: Error logging response generation: {str(e)}")

async def get_relevant_feedback(transcript: str, uid: str, company_from_session: Optional[str] = None, organization_from_session: Optional[str] = None) -> list:
    print(f"[DEBUG] get_relevant_feedback: Entered function with transcript_length={len(transcript)}, uid={uid}")
    try:
        db_client = get_firestore_client()
        print("[DEBUG] get_relevant_feedback: Firestore client initialized.")
        
        user_company = company_from_session
        user_organization = organization_from_session

        if not user_company:
            user_ref = db_client.collection('users').document(uid)
            user_doc = user_ref.get()
            print(f"[DEBUG] get_relevant_feedback: User doc for uid {uid} exists: {user_doc.exists}")
            if user_doc.exists:
                user_profile_data = user_doc.to_dict()
                if user_profile_data:
                    user_company = user_profile_data.get('company')
                    user_organization = user_profile_data.get('organization')

        keywords = set([word.lower() for word in re.findall(r'\b\w+\b', transcript) 
                        if len(word) > 3 and word.lower() not in {
                            'this', 'that', 'with', 'from', 'have', 'what',
                            'when', 'where', 'which', 'would', 'could', 'should'
                        }])
        
        feedback_ref = db_client.collection('feedback')
        queries_to_run = []

        if user_company and user_organization:
            queries_to_run.append(feedback_ref.where('company', '==', user_company).where('organization', '==', user_organization).where('isHelpful', '==', False).limit(3))
            queries_to_run.append(feedback_ref.where('company', '==', user_company).where('organization', '==', user_organization).where('isHelpful', '==', True).limit(2))
        if user_company:
            queries_to_run.append(feedback_ref.where('company', '==', user_company).where('isHelpful', '==', False).limit(5))
            queries_to_run.append(feedback_ref.where('company', '==', user_company).where('isHelpful', '==', True).limit(3))
        queries_to_run.append(feedback_ref.where('company', 'in', [None, ""]).where('isHelpful', '==', False).limit(5))
        queries_to_run.append(feedback_ref.where('company', 'in', [None, ""]).where('isHelpful', '==', True).limit(3))
        
        all_feedback_items = []
        processed_ids = set()

        for q in queries_to_run:
            docs = q.stream()
            for doc in docs:
                if doc.id in processed_ids:
                    continue
                data = doc.to_dict()
                if data and 'context' in data and 'transcript' in data['context']:
                    context_text = data['context']['transcript'].lower()
                    matching_keywords = sum(1 for keyword in keywords if keyword in context_text)
                    if matching_keywords > 0:
                        all_feedback_items.append({
                            'feedback_id': doc.id,
                            'feedback_data': data,
                            'relevance_score': matching_keywords,
                            'isHelpful': data.get('isHelpful', False)
                        })
                        processed_ids.add(doc.id)
        
        all_feedback_items.sort(key=lambda x: (x['relevance_score'], x['isHelpful']), reverse=True)
        
        final_feedback = sorted([f for f in all_feedback_items if not f['isHelpful']], key=lambda x: x['relevance_score'], reverse=True)[:3]
        final_feedback.extend(sorted([f for f in all_feedback_items if f['isHelpful']], key=lambda x: x['relevance_score'], reverse=True)[:2])
        
        print(f"[DEBUG] get_relevant_feedback: Returning {len(final_feedback)} feedback items.")
        return final_feedback
        
    except Exception as e:
        print(f"[ERROR] get_relevant_feedback: Error retrieving feedback: {str(e)}")
        print(f"[TRACEBACK] get_relevant_feedback: {traceback.format_exc()}")
        return []

response_cache: dict[str, ResponseData] = {}

@router.post("/generate-response", response_model=ResponseData)
async def generate_response(request: ResponseRequest, user: AuthorizedUser, background_tasks: BackgroundTasks) -> ResponseData:
    print(f"[DEBUG] generate_response: Entered function. Session ID: {request.session_id}, UID: {request.uid}")
    notes_for_response = []
    user_has_feedback_already = False

    firestore_client = None
    tts_client = None

    try:
        firestore_client = get_firestore_client()
        
        creds_dict = get_firebase_credentials_dict()
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        tts_client = texttospeech.TextToSpeechClient(credentials=creds)
        
        print("[DEBUG] Firestore and TTS clients initialized using centralized config.")
        print(f"[TTS_DEBUG] tts_client initialized: {type(tts_client)}")
    except Exception as e_cred:
        error_msg = f"Failed to initialize GCP clients: {str(e_cred)}"
        print(f"[ERROR] {error_msg}")
        notes_for_response.append(error_msg)
        firestore_client = None
        tts_client = None

    try:
        if firestore_client:
            try:
                feedback_ref = firestore_client.collection('feedback')
                query = feedback_ref.where('sessionId', '==', request.session_id).where('userId', '==', request.uid).limit(1)
                if any(query.stream()):
                    user_has_feedback_already = True
                print(f"[DEBUG] Existing feedback check. Found: {user_has_feedback_already}")
            except Exception as e_fb_check:
                notes_for_response.append(f"Failed to check feedback: {str(e_fb_check)}")
        else:
            notes_for_response.append("Skipped feedback check: Firestore client NA.")

        cache_key = f"{request.session_id}_{hash(request.transcript + ''.join(sorted(request.media_urls or [])))}"
        if cache_key in response_cache:
            print(f"[DEBUG] Cache hit for session {request.session_id}.")
            cached_data = response_cache[cache_key]
            if isinstance(cached_data, ResponseData):
                return cached_data

        #gemini_api_key = db.secrets.get("GOOGLE_GEMINI_API_KEY")
        #if not gemini_api_key:
        #    error_msg = "GOOGLE_GEMINI_API_KEY not found. Cannot call Gemini."
        #    print(f"[ERROR] {error_msg}")
        #    notes_for_response.append(error_msg)
        #    return ResponseData(text_response="ERROR: AI model config issue.", status="error", notes="\n".join(notes_for_response) or error_msg, user_has_submitted_feedback=user_has_feedback_already)
        
        model = get_gemini_client()
        print("[DEBUG] Gemini API configured with gemini-2.5-flash.")

        prompt_contexts = {"feedback": "", "knowledge": "", "web": ""}
        knowledge_sources_used = []
        web_sources_used = []
        user_data_for_context = {}
        
        constraints_text = None
        constraint_stats = {"count": 0, "by_severity": {}, "by_category": {}}

        if firestore_client:
            try:
                user_doc_ref = firestore_client.collection('users').document(request.uid)
                user_doc = user_doc_ref.get()
                if user_doc.exists:
                    user_data_for_context = user_doc.to_dict()
                    print(f"[DEBUG] Fetched user data: Company {user_data_for_context.get('company')}")
                else:
                    notes_for_response.append(f"User doc not found for UID: {request.uid}")
            except Exception as e_user_fetch:
                notes_for_response.append(f"Error fetching user data: {str(e_user_fetch)}")

            try:
                user_company = user_data_for_context.get('company')
                user_domain = user_data_for_context.get('assignedDomain')
                
                if user_company and user_domain:
                    print(f"[CONSTRAINT] 🔍 Fetching constraints for company '{user_company}' in domain '{user_domain}'...")
                    
                    active_constraints = await asyncio.to_thread(
                        get_active_constraints,
                        user_id=request.uid,
                        domain=user_domain
                    )
                    
                    if active_constraints:
                        print(f"[CONSTRAINT] ✅ Found {len(active_constraints)} active constraints")
                        
                        constraints_text = format_constraints_for_gemini(active_constraints)
                        
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

            try:
                session_company = user_data_for_context.get('company', None)
                session_org = request.session_organization or user_data_for_context.get('organization', None)
    
                relevant_feedback_items = await get_relevant_feedback(request.transcript, request.uid, session_company, session_org)
                if relevant_feedback_items:
                    fb_ctx_builder = ["\nPREVIOUS FEEDBACK TO CONSIDER:\n"]
                    for i, item in enumerate(relevant_feedback_items, 1):
                        feedback = item['feedback_data']
                        was_helpful = "HELPFUL" if feedback.get('isHelpful', False) else "NOT HELPFUL"
                        original_transcript = feedback.get('context', {}).get('transcript', 'Unknown issue')
                        comment = feedback.get('comment', '')
                        fb_ctx_builder.append(f"\n{i}. SIMILAR ISSUE: {original_transcript} (Marked as: {was_helpful})")
                        if comment: fb_ctx_builder.append(f"    USER COMMENT: {comment}")
                    prompt_contexts["feedback"] = "".join(fb_ctx_builder)
                print(f"[DEBUG] get_relevant_feedback returned {len(relevant_feedback_items)} items.")
            except Exception as e_get_fb:
                notes_for_response.append(f"Error getting relevant feedback: {str(e_get_fb)}")
            
            rag_succeeded = False
            
            if request.use_knowledge_base and user_data_for_context.get('company'):
                print(f"[RAG_DEBUG_RESPONSE_GEN] Attempting RAG. use_knowledge_base={request.use_knowledge_base}, company={user_data_for_context.get('company')}, query='{request.transcript[:50]}...'")
                try:
                    retrieval_req_obj = RetrievalRequest(
                        query=request.transcript, 
                        company=user_data_for_context.get('company'), 
                        max_results=3,
                        media_urls=request.media_urls,
                        score_threshold=0.5
                    )
                    retrieval_response = retrieve_knowledge(user=user, request=retrieval_req_obj)
                    
                    if retrieval_response and retrieval_response.chunks and len(retrieval_response.chunks) > 0:
                        kn_ctx_builder = ["\nRELEVANT KNOWLEDGE BASE INFORMATION:\n"]
                        for i, chunk in enumerate(retrieval_response.chunks, 1):
                            if chunk.metadata.get('type') == 'image':
                                context_line = f"\n[{i}] [Image Description] {chunk.content}\n"
                            else:
                                context_line = f"\n[{i}] [Text Document] {chunk.content}\n"
                            
                            kn_ctx_builder.append(context_line)
                            knowledge_sources_used.append({
                                "title": chunk.metadata.get('title', 'Document Chunk'), 
                                "score": chunk.score, 
                                "id": chunk.id,
                                "type": chunk.metadata.get('type', 'text')
                            })
                        prompt_contexts["knowledge"] = "".join(kn_ctx_builder)
                        rag_succeeded = True
                        print(f"[RAG_DEBUG_RESPONSE_GEN] RAG SUCCESS: Retrieved {len(retrieval_response.chunks)} chunks. Web search will be SKIPPED.")
                        print(f"[DEBUG] RAG: Retrieved {len(retrieval_response.chunks)} chunks.")
                    else:
                        print("[RAG_DEBUG_RESPONSE_GEN] RAG returned 0 chunks. Will attempt web search as fallback.")
                        notes_for_response.append("RAG returned no results. Using web search as fallback.")
                        
                except Exception as e_rag:
                    print(f"[RAG_DEBUG_RESPONSE_GEN] RAG FAILED with error: {str(e_rag)}. Will attempt web search as fallback.")
                    notes_for_response.append(f"Error during RAG: {str(e_rag)}\n{traceback.format_exc()}")
                    notes_for_response.append("RAG failed. Using web search as fallback.")
        else:
            notes_for_response.append("Skipped RAG & Feedback: Firestore client NA.")
        
        if not rag_succeeded:
            print("[WEB_SEARCH_FALLBACK] RAG did not return sufficient results. Attempting web search as fallback...")
            try:
                web_search_req_obj = WebSearchRequest(query=request.transcript, search_depth="advanced", max_results=3)
                web_search_resp_obj = search_web(request=web_search_req_obj, user=user)
                if web_search_resp_obj and web_search_resp_obj.results:
                    web_ctx_builder = ["\nRELEVANT COMMUNITY & TECHNICAL KNOWLEDGE (from Web):\n"]
                    start_idx = len(knowledge_sources_used) + 1
                    for i, result_item in enumerate(web_search_resp_obj.results, start_idx):
                        web_ctx_builder.append(f"\n[{i}] {result_item.title}\n{result_item.content}\n(Source: {result_item.url})\n")
                        web_sources_used.append({"title": result_item.title, "url": result_item.url, "source": result_item.source})
                    prompt_contexts["web"] = "".join(web_ctx_builder)
                    print(f"[WEB_SEARCH_FALLBACK] Web Search SUCCESS: Retrieved {len(web_search_resp_obj.results)} results.")
                else:
                    print("[WEB_SEARCH_FALLBACK] Web search returned no results.")
            except Exception as e_web:
                print(f"[WEB_SEARCH_FALLBACK] Web search FAILED: {str(e_web)}")
                notes_for_response.append(f"Error during web search fallback: {str(e_web)}\n{traceback.format_exc()}")
        else:
            print("[WEB_SEARCH_FALLBACK] SKIPPED - RAG returned sufficient results.")

        company_name_ctx = user_data_for_context.get('company', 'your company')
        org_name_ctx = request.session_organization or user_data_for_context.get('organization', 'your current department')
        company_info_for_prompt = f"You are supporting a technician at {company_name_ctx}"
        if org_name_ctx and org_name_ctx != company_name_ctx: 
            company_info_for_prompt += f" in the {org_name_ctx} department"

        constraints_section = ""
        if constraints_text:
            print(f"[CONSTRAINT_DEBUG] Injecting constraints into response generation prompt: {constraints_text[:200]}...")
            constraints_section = f"\n\n{constraints_text}\n"

        rag_summary_parts = []
        if knowledge_sources_used:
            rag_summary_parts.append(f"Internal docs: {len(knowledge_sources_used)}")
        if web_sources_used:
            rag_summary_parts.append(f"Web results: {len(web_sources_used)}")
        
        if not rag_summary_parts:
            rag_summary = "No specific knowledge found."
        else:
            rag_summary = " ".join(rag_summary_parts)

        conversation_history_str = ""
        if request.history:
            for msg in request.history:
                conversation_history_str += f"\n**{msg.role.capitalize()}**: {msg.content}"

        text_prompt = (
            f"You are an expert AI technical assistant for field technicians. {company_info_for_prompt}.\n"
            f"{constraints_section}"
            f"Context: {rag_summary}\n\n"
            "--- CONVERSATION HISTORY ---"
            f"{conversation_history_str}\n"
            "--------------------------\n\n"
            f"TECHNICIAN'S LATEST QUERY: \"{request.transcript}\"\n"
            f"{prompt_contexts['feedback']}"
            f"{prompt_contexts['knowledge']}"
            f"{prompt_contexts['web']}\n"
            "Based on the full conversation, the latest query, visual media (if any), feedback, and knowledge, provide a Markdown response:\n"
            "- Initial Assessment\n- Step-by-Step Instructions\n- Guardrails\n- Safety Precautions\n- Additional Notes\n"
            "Prioritize internal knowledge. Cite sources [1], [2], etc. from the knowledge sections. Address the LATEST query directly."
        )
        prompt_parts = [text_prompt]

        gcs_client_for_media = None
        if request.media_urls:
            print(f"[DEBUG] Processing {len(request.media_urls)} media URLs.")
            try:
                creds_dict = get_firebase_credentials_dict()
                creds = service_account.Credentials.from_service_account_info(creds_dict)
                gcs_client_for_media = storage.Client(credentials=creds)
                print("[DEBUG] GCS client for media initialized.")

                for media_url in request.media_urls:
                    if not media_url.startswith("gs://"):
                        notes_for_response.append(f"Skipping invalid media URL: {media_url}")
                        continue
                    
                    bucket_name, blob_name = media_url.replace("gs://", "").split("/", 1)
                    blob = gcs_client_for_media.bucket(bucket_name).blob(blob_name)
                    media_bytes = blob.download_as_bytes()
                    
                    mime_type, _ = mimetypes.guess_type(blob_name)
                    
                    if not mime_type or mime_type == "application/octet-stream":
                        if blob_name.lower().endswith(('.jpg', '.jpeg')):
                            mime_type = 'image/jpeg'
                        elif blob_name.lower().endswith('.png'):
                            mime_type = 'image/png'
                        elif blob_name.lower().endswith('.webp'):
                            mime_type = 'image/webp'
                        else:
                            notes_for_response.append(f"Skipping media with unknown type: {blob_name}")
                            print(f"[WARN] Skipping media with unknown MIME type: {blob_name}")
                            continue
                    
                    print(f"[DEBUG] Media from GCS: {len(media_bytes)} bytes, MIME: {mime_type}")

                    encoded_data = base64.b64encode(media_bytes).decode('utf-8')
                    prompt_parts.append({"mime_type": mime_type, "data": encoded_data})
            except Exception as e_media:
                notes_for_response.append(f"Error processing media: {str(e_media)}\n{traceback.format_exc()}")
        
        print(f"[DEBUG] Calling Gemini. Prompt parts: {len(prompt_parts)}. Text prompt len: {len(text_prompt)}")
        gemini_response_obj = model.generate_content(prompt_parts, model='gemini-2.5-flash')
        generated_text_response = gemini_response_obj
        print(f"[DEBUG] Gemini response received. Length: {len(generated_text_response)}")
        
        # Schedule TTS processing in background (non-blocking)
        audio_response_url = None
        if tts_client and generated_text_response:
            print("[TTS_DEBUG] Scheduling TTS processing in background")
            background_tasks.add_task(
                process_tts_async,
                session_id=request.session_id,
                command_id=request.command_id,
                text=generated_text_response,
                tts_client=tts_client
            )
            print("[TTS_DEBUG] TTS task scheduled, continuing with response")
        else:
            print(f"[TTS_DEBUG] Skipped TTS scheduling. tts_client: {bool(tts_client)}, generated_text_response: {bool(generated_text_response)}")
            notes_for_response.append("Skipped TTS: client NA or no text.")
        
        final_response_data = ResponseData(
            text_response=generated_text_response,
            audio_url=audio_response_url,
            user_has_submitted_feedback=user_has_feedback_already,
            status="success",
            notes="\n".join(notes_for_response) if notes_for_response else None,
            knowledge_sources_used=knowledge_sources_used or None,
            web_sources_used=web_sources_used or None
        )

        if firestore_client and request.command_id:
            try:
                command_ref = firestore_client.collection('troubleshootingSessions').document(request.session_id).collection('voiceCommands').document(request.command_id)
                command_ref.update({
                    'response': final_response_data.text_response,
                    'responseTimestamp': SERVER_TIMESTAMP,
                    'responseAudioUrl': final_response_data.audio_url
                })
                print(f"[DEBUG] Successfully logged AI response back to command {request.command_id}")
            except Exception as e_final_log:
                print(f"[ERROR] Failed to log final AI response back to command document: {str(e_final_log)}")
                final_response_data.notes = (final_response_data.notes or "") + f"\nFailed to save response to command doc: {e_final_log}"

        if firestore_client:
            try:
                session_doc_ref = firestore_client.collection('troubleshootingSessions').document(request.session_id)
                session_update_data = {
                    'lastUpdated': SERVER_TIMESTAMP,
                    'status': 'processing_audio',
                    'responseAudioUrl': final_response_data.audio_url,
                }
                session_doc_ref.set(session_update_data, merge=True)
                print(f"[DEBUG] Successfully updated parent session {request.session_id} status and timestamp.")
            except Exception as e_session_update:
                print(f"[ERROR] Failed to update parent session document: {str(e_session_update)}")
                final_response_data.notes = (final_response_data.notes or "") + f"\nFailed to update session status: {e_session_update}"

        response_cache[cache_key] = final_response_data
        if len(response_cache) > 20: 
            response_cache.pop(list(response_cache.keys())[0])

        if firestore_client:
            try:
                log_user_data = user_data_for_context.copy()
                log_user_data['uid'] = request.uid
                log_user_data['email'] = user.email
                
                await log_response_generation(
                    log_user_data, request.transcript, 
                    bool(knowledge_sources_used), knowledge_sources_used,
                    bool(web_sources_used), web_sources_used, generated_text_response,
                    constraint_stats
                )
                print("[DEBUG] Response generation logged.")
            except Exception as e_log:
                print(f"[ERROR] Error logging response (post-creation): {str(e_log)}")
                final_response_data.notes = (final_response_data.notes or "") + f"\nFailed to log generation event: {e_log}"

        print(f"[INFO] generate_response successful for session {request.session_id}")
        return final_response_data

    except Exception as e_main:
        crit_msg = f"CRITICAL Unhandled Exception: {str(e_main)}"
        print(f"[CRITICAL ERROR] {crit_msg}\n{traceback.format_exc()}")
        notes_for_response.append(crit_msg)
        return ResponseData(
            text_response="Critical error generating response. Contact support.",
            status="error",
            notes="\n".join(notes_for_response) or crit_msg,
            user_has_submitted_feedback=user_has_feedback_already
        )
