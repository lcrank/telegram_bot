import os

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"]
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "friday-secret-key")
WS_PORT = int(os.environ.get("PORT", os.environ.get("WS_PORT", 8080)))
ADMIN_USER_IDS = [int(x) for x in os.environ.get("ADMIN_USER_IDS", "").split(",") if x]

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
SITE_URL = os.environ.get("SITE_URL", "https://github.com/friday-assistant")
SITE_NAME = os.environ.get("SITE_NAME", "FridayBot")
