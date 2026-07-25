import logging
import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/stt",
    tags=["STT"],
)

@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribes an uploaded audio chunk using OpenAI's Whisper model (whisper-1).
    Used by the Chrome extension to provide chunked live context.
    """
    settings = get_settings()
    
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        # Read the audio file bytes
        audio_content = await audio.read()
        logger.info(f"Received audio chunk: {len(audio_content)} bytes")
        
        # We must use a synchronous httpx call inside async or an async client.
        # It's cleaner to use async httpx here to hit the REST API directly.
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {
                "file": (audio.filename or "chunk.webm", audio_content, audio.content_type or "audio/webm")
            }
            data = {
                "model": "whisper-1"
            }
            
            response = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}"
                },
                data=data,
                files=files
            )
            
            response.raise_for_status()
            result = response.json()
            text = result.get("text", "").strip()
            
            logger.info(f"Successfully transcribed chunk: '{text}'")
            return {"text": text}

    except httpx.HTTPStatusError as e:
        logger.error(f"OpenAI Whisper error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=502, detail="Failed to transcribe audio via OpenAI")
    except Exception as e:
        logger.error(f"Error processing audio upload: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during transcription")
