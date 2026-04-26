# src/app/apis/audio_files/__init__.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import databutton as db
import io

router = APIRouter(prefix="/audio_files")

# Ensure tags=["stream"] is present
@router.get("/stream/{filename}", tags=["stream"])
async def stream_audio_file(filename: str):
    """
    Streams an audio file stored in db.storage.binary.
    """
    try:
        print(f"[AUDIO_STREAM] Attempting to stream file: {filename}")
        audio_bytes = db.storage.binary.get(key=filename)
        
        if not audio_bytes:
            print(f"[AUDIO_STREAM] File not found: {filename}")
            raise HTTPException(status_code=404, detail="Audio file not found")
        
        print(f"[AUDIO_STREAM] File found, size: {len(audio_bytes)} bytes. Streaming now.")
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")

    except FileNotFoundError:
        print(f"[AUDIO_STREAM] FileNotFoundError for: {filename}")
        raise HTTPException(status_code=404, detail="Audio file not found (FileNotFound)")
    except Exception as e:
        print(f"[AUDIO_STREAM] Error streaming file {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error streaming audio: {str(e)}")
