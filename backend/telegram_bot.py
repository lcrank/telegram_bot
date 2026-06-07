import io
import base64
import json
import logging

from telegram import Update, Voice
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from .config import settings
from .stt import transcribe
from .agent import interpret_command
from .ws_manager import WSManager
from .tts import speak

logger = logging.getLogger(__name__)


def _allowed_ids() -> list[int]:
    raw = settings.TELEGRAM_ALLOWED_USER_IDS.strip()
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _is_allowed(user_id: int) -> bool:
    ids = _allowed_ids()
    if not ids:
        return True
    return user_id in ids


def _format_result(command: dict, result: dict) -> str:
    action = command.get("action", "")
    status = result.get("status", "error")

    if status == "error":
        return f"Error: {result.get('message', 'Unknown error')}"

    if action == "open_app":
        return f"Opened {command.get('target', '')}"
    if action == "close_app":
        return f"Closed {command.get('target', '')}"
    if action == "screenshot":
        return "Screenshot taken"
    if action == "type":
        return f"Typed: {command.get('text', '')[:60]}"
    if action == "hotkey":
        return f"Pressed {command.get('keys', '')}"
    if action == "shell":
        out = result.get("result", "")
        return f"Output:\n{out[:500]}"
    if action == "open_url":
        return f"Opened {command.get('url', '')}"
    if action == "clipboard_read":
        return f"Clipboard: {result.get('result', '')[:300]}"
    if action == "set_volume":
        return f"Volume set to {command.get('level', '')}%"
    return f"Done: {result.get('result', '')}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_allowed(user.id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text(
        "I'm online and ready. Send me a voice message or text to control your laptop."
    )


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_allowed(user.id):
        return

    voice = update.message.voice
    if not voice:
        return

    ws_manager: WSManager = context.bot_data["ws_manager"]
    if not ws_manager.is_connected:
        await update.message.reply_text("Laptop agent is offline.")
        return

    voice_file = await voice.get_file()
    audio_bytes = await voice_file.download_as_bytearray()

    try:
        transcript = await transcribe(bytes(audio_bytes))
    except Exception as e:
        logger.error(f"STT failed: {e}")
        await update.message.reply_text("Couldn't understand the audio. Please speak clearly.")
        return

    if not transcript:
        await update.message.reply_text("Got an empty transcript. Please try again.")
        return

    logger.info(f"Transcript from {user.id}: {transcript!r}")
    await update.message.reply_text(f"Heard: {transcript}\nProcessing...")

    try:
        command = await interpret_command(transcript)
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        await update.message.reply_text(f"Couldn't interpret command: {e}")
        return

    if command.get("action") == "clarify":
        question = command["question"]
        await update.message.reply_text(question)
        try:
            tts_audio = await speak(question)
            await update.message.reply_voice(io.BytesIO(tts_audio))
        except Exception as e:
            logger.warning(f"TTS failed: {e}")
        return

    if command.get("action") == "error":
        msg = command.get("message", "Unknown error")
        await update.message.reply_text(f"Error: {msg}")
        try:
            tts_audio = await speak(f"Sorry, {msg}")
            await update.message.reply_voice(io.BytesIO(tts_audio))
        except Exception:
            pass
        return

    try:
        result = await ws_manager.send_command(command, wa_id=str(user.id))
    except RuntimeError as e:
        await update.message.reply_text(str(e))
        return

    reply = _format_result(command, result)
    await update.message.reply_text(reply)

    try:
        tts_text = reply[:200]
        tts_audio = await speak(tts_text)
        await update.message.reply_voice(io.BytesIO(tts_audio))
    except Exception as e:
        logger.warning(f"TTS failed: {e}")

    if command.get("action") == "screenshot" and result.get("screenshot"):
        try:
            image_bytes = base64.b64decode(result["screenshot"])
            await update.message.reply_photo(io.BytesIO(image_bytes), caption="Current screen")
        except Exception as e:
            logger.error(f"Failed to send screenshot: {e}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_allowed(user.id):
        return

    ws_manager: WSManager = context.bot_data["ws_manager"]
    if not ws_manager.is_connected:
        await update.message.reply_text("Laptop agent is offline.")
        return

    text = update.message.text.strip()
    if not text:
        return

    logger.info(f"Text from {user.id}: {text!r}")

    try:
        command = await interpret_command(text)
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        await update.message.reply_text(f"Couldn't interpret command: {e}")
        return

    if command.get("action") == "clarify":
        question = command["question"]
        await update.message.reply_text(question)
        try:
            tts_audio = await speak(question)
            await update.message.reply_voice(io.BytesIO(tts_audio))
        except Exception:
            pass
        return

    if command.get("action") == "error":
        msg = command.get("message", "Unknown error")
        await update.message.reply_text(f"Error: {msg}")
        return

    try:
        result = await ws_manager.send_command(command, wa_id=str(user.id))
    except RuntimeError as e:
        await update.message.reply_text(str(e))
        return

    reply = _format_result(command, result)
    await update.message.reply_text(reply)

    try:
        tts_audio = await speak(reply[:200])
        await update.message.reply_voice(io.BytesIO(tts_audio))
    except Exception:
        pass

    if command.get("action") == "screenshot" and result.get("screenshot"):
        try:
            image_bytes = base64.b64decode(result["screenshot"])
            await update.message.reply_photo(io.BytesIO(image_bytes), caption="Current screen")
        except Exception as e:
            logger.error(f"Failed to send screenshot: {e}")


def create_application(ws_manager: WSManager) -> Application:
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

    app.bot_data["ws_manager"] = ws_manager

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE & ~filters.COMMAND, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app
