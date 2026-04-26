from fastapi import APIRouter, HTTPException, Body, File, UploadFile, Form
from pydantic import BaseModel, Field
from typing import Optional
import databutton as db
import tempfile
import os
import json
import time
from google.cloud import speech  # type: ignore
from google.oauth2 import service_account  # type: ignore
import base64
import re
from app.libs.firebase_config import get_firebase_credentials_dict


router = APIRouter()

class FeedbackTranscriptionRequest(BaseModel):
    feedback_id: str = Field(..., description="The ID of the feedback to transcribe")
    audio_data: str = Field(..., description="Base64 encoded audio data")

class FeedbackTranscriptionResponse(BaseModel):
    feedback_id: str = Field(..., description="The ID of the feedback that was transcribed")
    transcript: str = Field(..., description="The transcribed feedback")

# Define a function to sanitize storage keys
def sanitize_storage_key(key: str) -> str:
    """Sanitize storage key to only allow alphanumeric and ._- symbols"""
    return re.sub(r'[^a-zA-Z0-9._-]', '', key)

@router.post("/transcribe-feedback")
def transcribe_feedback(request: FeedbackTranscriptionRequest) -> FeedbackTranscriptionResponse:
    """Transcribe audio feedback using Google Cloud Speech-to-Text"""

    # Initialize variables for temporary files
    credentials_path = None
    audio_file_path = None

    try:
        # Decode the base64 audio data
        audio_data = base64.b64decode(request.audio_data.split(',')[1] if ',' in request.audio_data else request.audio_data)
        
        # Get Google Cloud credentials from centralized config
        creds_dict = get_firebase_credentials_dict()
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        
        
        # Setup temporary audio file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as audio_file:
            audio_file.write(audio_data)
            audio_file_path = audio_file.name
        
        # Initialize Speech-to-Text client
        client = speech.SpeechClient(credentials=credentials)
        
        # Create a storage key for the audio file
        timestamp = int(time.time())
        storage_key = sanitize_storage_key(f"feedback_audio_{request.feedback_id}_{timestamp}.mp3")
        
        # Store the audio file
        with open(audio_file_path, 'rb') as f:
            audio_content = f.read()
            db.storage.binary.put(storage_key, audio_content)
        
        # Perform speech recognition
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.MP3,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
        )
        
        # Detect speech in the audio file
        response = client.recognize(config=config, audio=audio)
        
        # Extract transcript from the response
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript
        
        # Create the response
        return FeedbackTranscriptionResponse(
            feedback_id=request.feedback_id,
            transcript=transcript
        )
    
    except Exception as e:
        error_message = f"Error transcribing feedback: {str(e)}"
        print(error_message)
        raise HTTPException(status_code=500, detail=error_message)
    
    finally:
        # Clean up temporary files
        if credentials_path and os.path.exists(credentials_path):
            os.unlink(credentials_path)
        if audio_file_path and os.path.exists(audio_file_path):
            os.unlink(audio_file_path)
