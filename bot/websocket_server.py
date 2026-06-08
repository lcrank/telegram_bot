import json
import asyncio
import logging
import uuid
from datetime import datetime
from websockets.asyncio.server import serve
from .config import AUTH_TOKEN, WS_PORT

logger = logging.getLogger(__name__)


class LaptopAgentManager:
    def __init__(self):
        self.connection = None
        self.authenticated = False
        self._pending = {}
        self._connected_at = None

    @property
    def is_connected(self):
        return self.connection is not None and self.authenticated

    @property
    def info(self):
        if self._connected_at:
            return {"connected": True, "since": self._connected_at.isoformat()}
        return {"connected": False}

    async def send_command(self, action, params=None):
        if not self.is_connected:
            return {"success": False, "error": "Laptop agent is not connected"}

        cmd_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self._pending[cmd_id] = future

        try:
            await self.connection.send(json.dumps({
                "type": "cmd",
                "id": cmd_id,
                "action": action,
                "params": params or {},
            }))
            result = await asyncio.wait_for(future, timeout=60.0)
            return result
        except asyncio.TimeoutError:
            self._pending.pop(cmd_id, None)
            return {"success": False, "error": "Command timed out after 60 seconds"}
        except Exception as e:
            self._pending.pop(cmd_id, None)
            return {"success": False, "error": str(e)}

    def resolve(self, cmd_id, result):
        future = self._pending.pop(cmd_id, None)
        if future and not future.done():
            future.set_result(result)

    async def handle_connection(self, websocket):
        logger.info("New WebSocket connection attempt")
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                t = data.get("type")

                if t == "auth":
                    if data.get("token") == AUTH_TOKEN:
                        self.connection = websocket
                        self.authenticated = True
                        self._connected_at = datetime.now()
                        await websocket.send(json.dumps({"type": "auth_ok"}))
                        logger.info("Laptop agent authenticated successfully")
                    else:
                        await websocket.send(json.dumps({
                            "type": "auth_error", "error": "Invalid token"
                        }))
                        await websocket.close()
                        break

                elif t == "result":
                    self.resolve(data.get("id"), data)

                elif t == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))

        except Exception as e:
            logger.warning(f"Laptop agent disconnected: {e}")
        finally:
            if self.connection == websocket:
                self.connection = None
                self.authenticated = False
                self._connected_at = None
                for cid, fut in self._pending.items():
                    if not fut.done():
                        fut.set_result({"success": False, "error": "Agent disconnected"})
                self._pending.clear()
                logger.info("Laptop agent cleaned up")


manager = LaptopAgentManager()


async def health_check(connection, request):
    if request.path in ("/", "/health"):
        return connection.respond(200, "OK")
    return None


async def start_websocket_server():
    async with serve(
        manager.handle_connection,
        "0.0.0.0",
        WS_PORT,
        process_request=health_check,
    ):
        logger.info(f"WebSocket server listening on port {WS_PORT}")
        await asyncio.Future()
