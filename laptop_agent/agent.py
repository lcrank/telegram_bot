"""
Laptop agent main loop.

Connects to the FastAPI backend via WebSocket, receives commands,
executes them locally, and sends results back.

Run with:
    python -m laptop_agent.agent
"""
import asyncio
import json
import logging
import signal
import sys

import websockets
from websockets.exceptions import ConnectionClosed

from .config import WS_URL, AGENT_SECRET, RECONNECT_DELAY
from .executor import dispatch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_shutdown = asyncio.Event()


def _handle_signal(*_):
    logger.info("Shutdown signal received")
    _shutdown.set()


async def run_agent() -> None:
    uri = f"{WS_URL}/agent?token={AGENT_SECRET}"
    logger.info(f"Connecting to {WS_URL} …")

    while not _shutdown.is_set():
        try:
            async with websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                logger.info("✅  Connected — waiting for commands")

                async for raw in ws:
                    if _shutdown.is_set():
                        break
                    try:
                        command = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning(f"Bad JSON from backend: {raw[:80]}")
                        continue

                    action = command.get("action", "?")
                    logger.info(f"← Received: {action}  {dict((k,v) for k,v in command.items() if k not in ('_request_id','_wa_id'))}")

                    result = await dispatch(command)

                    logger.info(f"→ Result: {result.get('status')}  {result.get('result','')[:80]}")
                    await ws.send(json.dumps(result))

        except ConnectionClosed as e:
            logger.warning(f"Connection closed: {e}. Reconnecting in {RECONNECT_DELAY}s …")
        except OSError as e:
            logger.warning(f"Connection error: {e}. Reconnecting in {RECONNECT_DELAY}s …")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)

        if not _shutdown.is_set():
            await asyncio.sleep(RECONNECT_DELAY)

    logger.info("Agent stopped.")


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    try:
        loop.run_until_complete(run_agent())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
