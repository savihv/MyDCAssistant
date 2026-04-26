from fastapi import APIRouter, UploadFile, File, HTTPException, Request # Response removed
from fastapi.responses import JSONResponse, Response # Response kept here
# Removed RequestValidationError and StarletteHTTPException imports as they are no longer used here
from pydantic import BaseModel
import tempfile
import os
import databutton as db
import time
from google.cloud import speech  # type: ignore
from google.oauth2 import service_account  # type: ignore
import io
import json
from app.libs.firebase_config import get_firebase_credentials_dict


router = APIRouter()

# Removed AudioUploadRequest Pydantic model for this endpoint
# class AudioUploadRequest(BaseModel):
#     audio: UploadFile

class TranscriptionResponse(BaseModel):
    transcription: str

@router.options("/transcribe-audio")
async def transcribe_audio_options():
    """Handle OPTIONS preflight requests for /transcribe-audio for CORS."""
    return Response(
        headers={
            "Access-Control-Allow-Origin": "*",  # IMPORTANT: Restrict this in production
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization", # Or be more specific
        }
    )

@router.post("/transcribe-audio", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...)) -> TranscriptionResponse: # Changed signature
    print("[BACKEND DEBUG] /transcribe-audio endpoint called.")
    # print(f"[BACKEND DEBUG] Request Headers: {request.headers}") # request object no longer available directly
    """Transcribe audio using Google Cloud Speech-to-Text with fallback to mock implementation"""

    use_mock = False
    audio_content_length = 0

    # audio_file is now directly 'audio' from the signature
    # No need for: 
    # form_data = await request.form()
    # audio_file = form_data.get("audio")
    # Validation for audio file presence is implicitly handled by FastAPI if File(...) is not optional
    # And type checking for UploadFile is also handled.

    print(f"[BACKEND DEBUG] Initializing variables. use_mock: {use_mock}")

    try:
        # Ensure 'audio' (the UploadFile) is not None if it were optional, though File(...) makes it required.
        if not audio:
            print("Audio file not received") # Should not happen with File(...)
            raise HTTPException(
                status_code=400,
                detail="Audio file not received. Ensure the file is sent with the key 'audio'."
            )


        if not use_mock:
            print(f"[BACKEND DEBUG] Reading audio content. File type: {audio.content_type}, Filename: {audio.filename}")
            audio_content = await audio.read() 
            audio_content_length = len(audio_content)
            print(f"[BACKEND DEBUG] Audio content read, size: {audio_content_length} bytes.")

            if audio_content_length == 0:
                print("[BACKEND DEBUG] ERROR: Audio content is empty after reading.")
                raise HTTPException(status_code=400, detail="Uploaded audio content is empty.")

            print("[BACKEND DEBUG] Getting Google Cloud credentials from db.secrets...")
            creds_dict = get_firebase_credentials_dict()
            credentials = service_account.Credentials.from_service_account_info(creds_dict)
            print("[BACKEND DEBUG] Google Cloud credentials obtained from db.secrets.")

            print("[BACKEND DEBUG] Initializing SpeechClient...")
            client = speech.SpeechClient(credentials=credentials)
            print("[BACKEND DEBUG] SpeechClient initialized.")

            print(f"[BACKEND DEBUG] Transcribing audio using Google Cloud Speech-to-Text. File type: {audio.content_type}")

            print("[BACKEND DEBUG] Preparing RecognitionConfig...")
            config = speech.RecognitionConfig(
                # encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16, # Let Google auto-detect
                # sample_rate_hertz=16000, # Let Google auto-detect
                language_code="en-US",
                enable_automatic_punctuation=True,
                # audio_channel_count=1, # Let Google auto-detect
            )

            audio_obj = speech.RecognitionAudio(content=audio_content)
            print("[BACKEND DEBUG] RecognitionAudio object prepared.")

            print("[BACKEND DEBUG] Sending audio to Google Cloud Speech-to-Text API...")
            google_response = client.recognize(config=config, audio=audio_obj)
            print(f"[BACKEND DEBUG] Received response from Google API. Raw response (first 200 chars): {str(google_response)[:200]}")

            transcription = ""
            if not google_response.results:
                print("[BACKEND DEBUG] Google API returned no results.")
            else:
                print(f"[BACKEND DEBUG] Google API returned {len(google_response.results)} result(s).")
                for i, result in enumerate(google_response.results):
                    if result.alternatives:
                        print(f"[BACKEND DEBUG] Result {i}, Alternative 0 transcript: {result.alternatives[0].transcript}")
                        transcription += result.alternatives[0].transcript
                    else:
                        print(f"[BACKEND DEBUG] Result {i} has no alternatives.")

            print(f"[BACKEND DEBUG] Final extracted transcription: '{transcription}'")
            print(f"[BACKEND DEBUG] Transcription successful (from Google): {transcription[:50] if transcription else 'Empty'}...")

            # Even with response_model, returning JSONResponse is fine if you need to add custom headers.
            # FastAPI will validate the content against TranscriptionResponse.
            return JSONResponse(
                content={"transcription": transcription},
                headers={"Access-Control-Allow-Origin": "*"} 
            )

        else:  # Mock implementation
            print("Using mock implementation for transcription")
            await audio.seek(0) # Ensure seek is awaited if it's an async file interface
            audio_data = await audio.read() # Ensure read is awaited
            size = len(audio_data)

            mock_transcription = f"This is a mock transcription of your {audio.content_type} file that is {size} bytes."

            if size > 0:
                mock_transcription += " I'm seeing an issue with the power supply. The voltage readings are inconsistent. Please check the connections and ensure the device is properly grounded."
            
            return JSONResponse(
                content={"transcription": mock_transcription},
                headers={"Access-Control-Allow-Origin": "*"}
            )

    except Exception as e:
        print(f"[BACKEND DEBUG] Entered main EXCEPTION block in transcribe_audio. {str(e)}")
        error_type_name = type(e).__name__
        print(f"[BACKEND DEBUG] Error Type: {error_type_name}")
        print(f"[BACKEND DEBUG] Error Details: {str(e)}")
        
        status_code = 500
        error_detail = f"Error transcribing audio: {str(e)}"

        if isinstance(e, HTTPException):
            print(f"[BACKEND DEBUG] Caught HTTPException. Original Status: {e.status_code}, Original Detail: {e.detail}")
            status_code = e.status_code 
            error_detail = e.detail 
        
        print(f"[BACKEND DEBUG] Preparing error JSONResponse. Status: {status_code}, Detail to be sent: {error_detail}")
        response_with_cors = JSONResponse(
            status_code=status_code, 
            content={"detail": error_detail},
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            }
        )
        print(f"[BACKEND DEBUG] Returning error JSONResponse from transcribe_audio.{str(e)}")
        return response_with_cors
