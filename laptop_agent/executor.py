"""
Command dispatcher.
Receives a structured command dict from the backend and routes it to the
appropriate action module.  Returns a result dict with status + result/message.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from .actions import apps, keyboard, mouse, screen, shell

logger = logging.getLogger(__name__)

# All blocking I/O and GUI operations run in this thread pool
_pool = ThreadPoolExecutor(max_workers=2)

# Set of valid action names
VALID_ACTIONS = {
    "open_app", "close_app", "screenshot", "type",
    "hotkey", "click", "scroll", "shell", "open_url",
    "clipboard_read", "set_volume",
}


async def dispatch(command: dict) -> dict:
    """
    Dispatch a command dict.  Returns a result dict:
      {"status": "ok", "result": "...", "_request_id": "..."}
      {"status": "error", "message": "...", "_request_id": "..."}
    """
    action = command.get("action")
    request_id = command.get("_request_id", "")
    wa_id = command.get("_wa_id", "")

    if action not in VALID_ACTIONS:
        return _err(f"Unknown action: {action!r}", request_id, wa_id)

    loop = asyncio.get_event_loop()

    try:
        if action == "open_app":
            result = await loop.run_in_executor(_pool, apps.open_app, command["target"])

        elif action == "close_app":
            result = await loop.run_in_executor(_pool, apps.close_app, command["target"])

        elif action == "screenshot":
            b64 = await loop.run_in_executor(_pool, screen.take_screenshot)
            return {"status": "ok", "result": "Screenshot taken", "screenshot": b64,
                    "_request_id": request_id, "_wa_id": wa_id}

        elif action == "type":
            result = await loop.run_in_executor(
                _pool, keyboard.type_text, command.get("text", "")
            )

        elif action == "hotkey":
            result = await loop.run_in_executor(
                _pool, keyboard.press_hotkey, command.get("keys", "")
            )

        elif action == "click":
            result = await loop.run_in_executor(
                _pool, mouse.move_and_click,
                command.get("x", 0), command.get("y", 0), command.get("button", "left")
            )

        elif action == "scroll":
            result = await loop.run_in_executor(
                _pool, mouse.scroll,
                command.get("direction", "down"), command.get("amount", 3)
            )

        elif action == "shell":
            result = await loop.run_in_executor(
                _pool, shell.run_shell, command.get("command", "")
            )

        elif action == "open_url":
            result = await loop.run_in_executor(_pool, shell.open_url, command.get("url", ""))

        elif action == "clipboard_read":
            result = await loop.run_in_executor(_pool, screen.read_clipboard)

        elif action == "set_volume":
            result = await loop.run_in_executor(
                _pool, shell.set_volume, command.get("level", 50)
            )

        else:
            return _err("Unhandled action", request_id, wa_id)

        return {"status": "ok", "result": str(result), "_request_id": request_id, "_wa_id": wa_id}

    except PermissionError as e:
        logger.warning(f"Permission denied: {e}")
        return _err(f"Not permitted: {e}", request_id, wa_id)
    except Exception as e:
        logger.error(f"Execution error for {action}: {e}", exc_info=True)
        return _err(str(e), request_id, wa_id)


def _err(message: str, request_id: str, wa_id: str) -> dict:
    return {"status": "error", "message": message,
            "_request_id": request_id, "_wa_id": wa_id}
