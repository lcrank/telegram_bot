"""
Speech-to-text using OpenAI Whisper (local model).
Falls back to OpenAI's hosted Whisper API if local model is not loaded.
"""
import io
import tempfile
import os
import asyncio
from functools import lru_cache

# ── Option A: local Whisper model (faster, private, free) ─────────────────────
try:
    import whisper as _whisper
    _USE_LOCAL = True
except ImportError:
    _USE_LOCAL = False

# ── Option B: OpenAI hosted Whisper API (no GPU needed) ───────────────────────
from openai import AsyncOpenAI
from .config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


@lru_cache(maxsize=1)
def _load_local_model():
    """Load the Whisper model once and cache it."""
    import whisper
    return whisper.load_model("base")   # swap to "small" or "medium" for better accuracy


async def transcribe(audio_bytes: bytes, language: str = "en") -> str:
    """
    Transcribe audio bytes to text.
    Tries local Whisper first; falls back to the OpenAI API.
    """
    if _USE_LOCAL:
        return await _transcribe_local(audio_bytes, language)
    else:
        return await _transcribe_api(audio_bytes, language)


async def _transcribe_local(audio_bytes: bytes, language: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run_local_whisper, audio_bytes, language)


def _run_local_whisper(audio_bytes: bytes, language: str) -> str:
    model = _load_local_model()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        result = model.transcribe(tmp_path, language=language, fp16=False)
        return result["text"].strip()
    finally:
        os.unlink(tmp_path)


async def _transcribe_api(audio_bytes: bytes, language: str) -> str:
    """Use OpenAI's hosted Whisper-1 API."""
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "voice.ogg"   # extension tells Whisper the format
    response = await _client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language=language,
    )
    return response.text.strip()
