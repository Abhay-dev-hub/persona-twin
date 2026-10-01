import os
import logging
from typing import Iterator
from fastapi import HTTPException

logger = logging.getLogger("persona_twin")

def clone_voice(voice_bytes: bytes, name: str, filename: str = "sample.mp3", content_type: str = "audio/mpeg") -> str:
    api_key = os.environ.get("FISH_API_KEY")
    if not api_key:
        logger.warning("FISH_API_KEY is not set. Cannot clone voice.")
        return ""
        
    try:
        from fishaudio import FishAudio
        client = FishAudio(api_key=api_key)
        
        # Pass a tuple to bypass the SDK type hint and force httpx to send filename + mime type
        voice_tuple = (filename, voice_bytes, content_type)
        
        voice = client.voices.create(
            title=f"Cloned Voice for {name}",
            voices=[voice_tuple],
            description="Cloned from uploaded sample",
            visibility="private"
        )
        return voice.id
    except Exception as e:
        logger.error(f"Failed to clone voice with Fish Audio: {e}")
        return ""


def generate_speech(text: str, voice_id: str):
    api_key = os.environ.get("FISH_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="FISH_API_KEY is not set.")
        
    try:
        from fishaudio import FishAudio
        client = FishAudio(api_key=api_key)
        
        return client.tts.stream(
            text=text,
            reference_id=voice_id,
            format="mp3",
            model="s2.1-pro-free"
        )
    except Exception as e:
        logger.error(f"Failed to generate speech: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate speech with Fish Audio.")

