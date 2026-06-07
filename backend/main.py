import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import settings
from .telegram_bot import create_application
from .ws_manager import WSManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
ws_manager = WSManager()
telegram_app = create_application(ws_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Backend starting up")
    await telegram_app.initialize()
    await telegram_app.start()
    if settings.WEBHOOK_URL:
        webhook_url = f"{settings.WEBHOOK_URL.rstrip('/')}/webhook"
        await telegram_app.bot.set_webhook(url=webhook_url)
        logger.info(f"Telegram webhook set to {webhook_url}")
    yield
    await telegram_app.stop()
    await telegram_app.shutdown()
    logger.info("Shutdown complete")


app = FastAPI(title="Telegram Laptop Agent", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.post("/webhook")
@limiter.limit(settings.RATE_LIMIT)
async def telegram_webhook(request: Request):
    data = await request.json()
    from telegram import Update
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


@app.websocket("/agent")
async def agent_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token", "")
    if token != settings.AGENT_SECRET:
        await websocket.close(code=1008)
        return

    await ws_manager.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            await ws_manager.receive_result(raw)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
