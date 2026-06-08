import asyncio
import logging

from bot.telegram_bot import run_bot
from bot.websocket_server import start_websocket_server

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting FRIDAY Assistant...")
    await asyncio.gather(
        run_bot(),
        start_websocket_server(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down")
