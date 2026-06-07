import os
from dotenv import load_dotenv

load_dotenv()

WS_URL: str = os.getenv("WS_URL", "ws://localhost:8000")
AGENT_SECRET: str = os.getenv("AGENT_SECRET", "change-me-to-a-long-random-string")
RECONNECT_DELAY: float = float(os.getenv("RECONNECT_DELAY", "5"))
