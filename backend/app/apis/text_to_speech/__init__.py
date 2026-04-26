from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import databutton as db
import os
import io
import hashlib
from google.cloud import texttospeech  # type: ignore
from google.oauth2 import service_account  # type: ignore
import traceback
from app.env import Mode, mode
from app.libs.firebase_config import get_firebase_credentials_dict


router = APIRouter()

class SynthesisRequest(BaseModel):
    text: str

class SynthesisResponse(BaseModel):
    audio_url: str

@router.post("/synthesize")
async def synthesize(request: SynthesisRequest) -> SynthesisResponse:
    """
    Synthesizes speech from text using Google Cloud Text-to-Speech,
    caches it in db.storage, and returns a URL for instant playback.
    """
    try:
        # Generate cache key based on text hash
        text_hash = hashlib.md5(request.text.encode('utf-8')).hexdigest()
        audio_filename = f"tts_cache_{text_hash}.mp3"
        
        # Check if audio already exists in cache
        try:
            existing_audio = db.storage.binary.get(key=audio_filename)
            if existing_audio:
                print(f"[TTS] Cache hit for {audio_filename}")
                # Return cached URL immediately
                relative_audio_path = f"/audio_files/stream/{audio_filename}"
                if mode == Mode.PROD:
                    base_url = "https://riff.new/_projects/24943f2a-846d-4587-b501-f26cc2851ea5/dbtn/prodx/app/routes"
                else:
                    base_url = "https://riff.new/_projects/24943f2a-846d-4587-b501-f26cc2851ea5/dbtn/devx/app/routes"
                
                audio_url = f"{base_url}{relative_audio_path}"
                return SynthesisResponse(audio_url=audio_url)
        except FileNotFoundError:
            print(f"[TTS] Cache miss for {audio_filename}, generating new audio")
        
        # Get credentials from secrets
        creds_dict = get_firebase_credentials_dict()
        credentials = service_account.Credentials.from_service_account_info(creds_dict)

        # Initialize the TTS client
        tts_client = texttospeech.TextToSpeechClient(credentials=credentials)

        # Chunk the text (same logic as before)
        text_chunks = []
        current_chunk = ""
        for line in request.text.splitlines():
            if len((current_chunk + line).encode('utf-8')) < 4500:
                current_chunk += line + "\n"
            else:
                text_chunks.append(current_chunk)
                current_chunk = line + "\n"
        if current_chunk:
            text_chunks.append(current_chunk)

        # Synthesize each chunk and collect audio bytes
        audio_chunks = []  # Collect MP3 bytes directly instead of using AudioSegment
        
        voice_params = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Studio-O")
        audio_config_params = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

        # Synthesize each chunk
        for i, chunk in enumerate(text_chunks):
            if not chunk.strip(): 
                continue
            
            print(f"[TTS] Processing chunk {i+1}/{len(text_chunks)} (Length: {len(chunk)})")
            synthesis_input = texttospeech.SynthesisInput(text=chunk)
            
            response = tts_client.synthesize_speech(
                input=synthesis_input, 
                voice=voice_params, 
                audio_config=audio_config_params
            )
            
            # Collect the MP3 bytes directly
            audio_chunks.append(response.audio_content)

        # Combine all audio chunks into single MP3
        # Note: This simple concatenation works for MP3 files
        audio_bytes = b''.join(audio_chunks)
        
        # Store in db.storage for caching
        db.storage.binary.put(key=audio_filename, value=audio_bytes)
        print(f"[TTS] Cached audio as {audio_filename}")
        
        # Construct URL
        relative_audio_path = f"/audio_files/stream/{audio_filename}"
        if mode == Mode.PROD:
            base_url = "https://riff.new/_projects/24943f2a-846d-4587-b501-f26cc2851ea5/dbtn/prodx/app/routes"
        else:
            base_url = "https://riff.new/_projects/24943f2a-846d-4587-b501-f26cc2851ea5/dbtn/devx/app/routes"
        
        audio_url = f"{base_url}{relative_audio_path}"
        
        return SynthesisResponse(audio_url=audio_url)

    except Exception as e:
        print(f"[ERROR][TTS] Failed to synthesize speech: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Failed to generate audio.")
