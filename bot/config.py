import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "friday-secret-key")
WS_PORT = int(os.environ.get("PORT", os.environ.get("WS_PORT", 8080)))

AI_PROVIDER = os.environ.get("AI_PROVIDER", "openrouter").lower()

if AI_PROVIDER == "gemini":
    AI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    if not AI_API_KEY:
        logger.warning("GEMINI_API_KEY is not set! AI features will not work.")
    AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
    AI_MODEL = os.environ.get("AI_MODEL", "gemini-2.0-flash")
else:
    AI_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
    if not AI_API_KEY:
        logger.warning("OPENROUTER_API_KEY is not set! AI features will not work.")
    AI_BASE_URL = "https://openrouter.ai/api/v1"
    AI_MODEL = os.environ.get("AI_MODEL", "openai/gpt-4o-mini")

SITE_URL = os.environ.get("SITE_URL", "https://github.com/friday-assistant")
SITE_NAME = os.environ.get("SITE_NAME", "FridayBot")
