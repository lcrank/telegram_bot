import io
from openai import AsyncOpenAI
from .config import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def speak(text: str, voice: str = "") -> bytes:
    voice = voice or settings.TTS_VOICE
    response = await _client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
        response_format="ogg",
    )
    return response.content
