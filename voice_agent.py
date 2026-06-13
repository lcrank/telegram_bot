"""
FRIDAY Voice Agent - Always-listening with wake word detection + two-way voice.
Uses openWakeWord (ONNX) for wake word detection - no API keys needed.
Records speech, transcribes via Whisper, sends to server AI, speaks response via TTS.

Dependencies: pip install openwakeword sounddevice numpy httpx pyttsx3
"""

import asyncio
import io
import json
import logging
import os
import sys
import tempfile
import threading
import time
import wave
import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import numpy as np
import sounddevice as sd
import httpx

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("voice_agent")


def _load_config():
    cfg_path = Path(__file__).parent / "agent_config.json"
    if cfg_path.exists():
        try:
            with open(cfg_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


_full_cfg = _load_config()
_cfg = _full_cfg.get("voice", {})

WAKE_WORD = os.environ.get("WAKE_WORD") or _cfg.get("wake_word", "hey_jarvis")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = int(os.environ.get("CHAT_ID", "0"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://openrouter.ai/api/v1")
SILENCE_DURATION = float(os.environ.get("SILENCE_DURATION") or _cfg.get("silence_duration", 1.5))
RECORD_TIMEOUT = float(os.environ.get("RECORD_TIMEOUT") or _cfg.get("record_timeout", 15.0))
SILENCE_THRESHOLD = int(os.environ.get("SILENCE_THRESHOLD") or _cfg.get("silence_threshold", 800))
WAKE_THRESHOLD = float(os.environ.get("WAKE_THRESHOLD") or _cfg.get("wake_threshold", 0.5))
AGENT_SERVER_URL = os.environ.get("AGENT_SERVER_URL") or _full_cfg.get("server_url", "ws://localhost:8080")
AGENT_AUTH_TOKEN = os.environ.get("AGENT_AUTH_TOKEN") or _full_cfg.get("auth_token", "friday-secret-key")

SAMPLE_RATE = 16000
FRAME_SIZE = 1280


class VoiceAgent:
    def __init__(self):
        self.wake_model = None
        self.model_name = None
        self.is_recording = False
        self.recorded_chunks = []
        self.silence_start = None
        self.record_start = None
        self.queue = None
        self.running = False
        self.sample_rate = SAMPLE_RATE
        self.ws = None

    async def _ensure_ws(self):
        if self.ws is not None:
            return True
        try:
            import websockets
            self.ws = await websockets.connect(AGENT_SERVER_URL, ping_interval=20, ping_timeout=10)
            await self.ws.send(json.dumps({
                "type": "auth", "token": AGENT_AUTH_TOKEN, "role": "voice",
            }))
            resp = json.loads(await self.ws.recv())
            if resp.get("type") == "auth_ok":
                logger.info("Voice agent connected to server via WebSocket")
                return True
            logger.error(f"Voice agent auth failed: {resp.get('error')}")
            await self.ws.close()
            self.ws = None
            return False
        except Exception as e:
            logger.warning(f"WebSocket connection failed: {e}")
            self.ws = None
            return False

    async def _close_ws(self):
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

    def start(self):
        try:
            from openwakeword import Model
        except ImportError:
            logger.error("openwakeword not installed. Run: pip install openwakeword")
            sys.exit(1)

        if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
            logger.error("TELEGRAM_BOT_TOKEN and CHAT_ID must be set.")
            sys.exit(1)

        logger.info(f"Loading wake word model '{WAKE_WORD}'...")
        try:
            self.wake_model = Model(
                wakeword_models=[WAKE_WORD],
                inference_framework="onnx",
            )
        except Exception as e:
            logger.error(f"Failed to load wake word model '{WAKE_WORD}': {e}")
            logger.error("Available models: alexa, hey_jarvis, hey_mycroft, hey_rhasspy")
            sys.exit(1)

        self.model_name = WAKE_WORD
        self.queue = asyncio.Queue()
        self.running = True

        logger.info(
            f"Voice agent started.\n"
            f"  Wake word: '{WAKE_WORD}'\n"
            f"  Threshold: {WAKE_THRESHOLD}\n"
            f"  Server: {AGENT_SERVER_URL}\n"
            "Listening..."
        )

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            callback=self.audio_callback,
            blocksize=FRAME_SIZE,
        )

        with stream:
            asyncio.run(self.event_loop())

    def audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"Audio status: {status}")

        audio = indata.flatten()

        if not self.is_recording:
            scores = self.wake_model.predict(audio)
            score = scores.get(self.model_name, 0.0)
            if score >= WAKE_THRESHOLD:
                logger.info(f"Wake word '{WAKE_WORD}' detected! (score: {score:.3f})")
                self.is_recording = True
                self.record_start = time.time()
                self.silence_start = None
                self.recorded_chunks = []
        else:
            self.recorded_chunks.append(audio.copy())

            max_amp = int(np.max(np.abs(audio)))
            if max_amp < SILENCE_THRESHOLD:
                if self.silence_start is None:
                    self.silence_start = time.time()
                elif (time.time() - self.silence_start) >= SILENCE_DURATION:
                    self._finish_recording()
            else:
                self.silence_start = None

            if self.is_recording and (time.time() - self.record_start) >= RECORD_TIMEOUT:
                self._finish_recording()

    def _finish_recording(self):
        if not self.is_recording:
            return
        self.is_recording = False
        self.wake_model.reset()
        if self.recorded_chunks:
            audio_data = np.concatenate(self.recorded_chunks)
            duration = len(audio_data) / self.sample_rate
            if duration > 0.3:
                logger.info(f"Recording finished: {duration:.1f}s")
                self.queue.put_nowait(("recording", audio_data))
            else:
                logger.info("Recording too short, discarding")

    async def event_loop(self):
        await self._ensure_ws()
        try:
            while self.running:
                event_type, data = await self.queue.get()
                if event_type == "recording":
                    await self._process_recording(data)
        finally:
            await self._close_ws()

    async def _process_recording(self, audio_data):
        logger.info("Transcribing...")
        wav_bytes = self._audio_to_wav(audio_data)

        text = await self._transcribe(wav_bytes)
        if not text or not text.strip():
            logger.info("No speech detected")
            return

        transcript = text.strip()
        logger.info(f"Transcribed ({len(transcript)} chars): {transcript[:200]}")

        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "voice_query", "text": transcript}))
                resp = json.loads(await asyncio.wait_for(self.ws.recv(), timeout=60.0))
                if resp.get("type") == "voice_response":
                    response_text = resp.get("text", "")
                    if response_text:
                        logger.info(f"AI response ({len(response_text)} chars): {response_text[:200]}")
                        await self._speak(response_text)
                        await self._send_to_telegram(f"🎤 {transcript}\n\n🤖 {response_text}")
                    else:
                        await self._send_to_telegram(f"🎤 {transcript}")
                else:
                    await self._send_to_telegram(f"🎤 {transcript}")
            except Exception as e:
                logger.warning(f"Voice query failed: {e}, falling back to Telegram")
                await self._send_to_telegram(f"🎤 {transcript}")
        else:
            await self._send_to_telegram(f"🎤 {transcript}")

    async def _speak(self, text):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception as e:
            logger.warning(f"TTS failed: {e}")

    def _audio_to_wav(self, audio_data):
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())
        return buf.getvalue()

    async def _transcribe(self, wav_bytes):
        if not OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY not set, skipping transcription")
            return None

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            tmp.write(wav_bytes)
            tmp.close()

            async with httpx.AsyncClient(timeout=30.0) as client:
                with open(tmp.name, "rb") as f:
                    files = {"file": ("speech.wav", f, "audio/wav")}
                    data = {"model": "whisper-1"}
                    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}

                    resp = await client.post(
                        f"{AI_BASE_URL}/audio/transcriptions",
                        headers=headers,
                        data=data,
                        files=files,
                    )
                    if resp.status_code == 200:
                        return resp.json().get("text", "").strip()
                    logger.warning(f"Whisper error: {resp.status_code} - {resp.text[:200]}")
                    return None
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    async def _send_to_telegram(self, text):
        if not TELEGRAM_BOT_TOKEN or not CHAT_ID:
            return
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": CHAT_ID, "text": text},
                )
                if resp.status_code != 200:
                    logger.warning(f"Telegram API error: {resp.status_code} - {resp.text[:200]}")
            except Exception as e:
                logger.warning(f"Failed to send to Telegram: {e}")

    def stop(self):
        self.running = False
        self.wake_model = None


def test_mic():
    duration = 3
    print(f"Recording for {duration} seconds (speak normally)...")
    recording = sd.rec(
        int(duration * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16"
    )
    sd.wait()
    audio = recording.flatten()
    max_amp = int(np.max(np.abs(audio)))
    rms = int(np.sqrt(np.mean(audio.astype(float) ** 2)))
    print(f"\nResults:")
    print(f"  Max amplitude: {max_amp}")
    print(f"  RMS: {rms}")
    suggested = max(max_amp // 2, 200)
    print(f"  Suggested SILENCE_THRESHOLD: {suggested}")
    print(f"  Suggested SILENCE_DURATION: 1.5")

    test_path = Path("test_mic.wav")
    with wave.open(str(test_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    print(f"\nSaved test recording to {test_path}")


def main():
    parser = argparse.ArgumentParser(description="FRIDAY Voice Agent")
    parser.add_argument("--test-mic", action="store_true", help="Test microphone and suggest settings")
    args = parser.parse_args()

    if args.test_mic:
        test_mic()
        return

    agent = VoiceAgent()
    try:
        agent.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        agent.stop()


if __name__ == "__main__":
    main()
