"""
Tests for the speech-to-text module.
Run with: pytest tests/test_stt.py -v
"""
import asyncio
import os
import pytest

# Patch settings before importing stt
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("AGENT_SECRET", "test-secret")

from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def sample_audio():
    """Minimal OGG file bytes (silent, just for API shape testing)."""
    return b"OggS" + b"\x00" * 100


def test_transcribe_returns_string(sample_audio):
    """transcribe() should return a non-empty string given valid audio."""
    with patch("backend.stt._USE_LOCAL", False), \
         patch("backend.stt._client") as mock_client:

        mock_client.audio.transcriptions.create = AsyncMock(
            return_value=MagicMock(text="open spotify")
        )

        result = asyncio.run(__import__("backend.stt", fromlist=["transcribe"]).transcribe(sample_audio))
        assert isinstance(result, str)
        assert result == "open spotify"


def test_transcribe_strips_whitespace(sample_audio):
    with patch("backend.stt._USE_LOCAL", False), \
         patch("backend.stt._client") as mock_client:

        mock_client.audio.transcriptions.create = AsyncMock(
            return_value=MagicMock(text="  take a screenshot  ")
        )
        from backend.stt import transcribe
        result = asyncio.run(transcribe(sample_audio))
        assert result == "take a screenshot"
