import json
import asyncio
import logging
import uuid
from datetime import datetime
from websockets.asyncio.server import serve
from .config import AUTH_TOKEN, WS_PORT

logger = logging.getLogger(__name__)

AI_ACTION_MAP = {
    "execute_shell": "shell", "list_files": "file_list",
    "read_file": "file_read", "write_file": "file_write",
    "get_system_info": "system_info", "take_screenshot": "screenshot",
    "press_key": "press_key", "type_text": "type_text",
    "mouse_click": "mouse_click", "mouse_move": "mouse_move",
    "launch_app": "launch_app", "clipboard_read": "clipboard_read",
    "clipboard_write": "clipboard_write",
}


class LaptopAgentManager:
    def __init__(self):
        self.laptop_connection = None
        self.voice_connection = None
        self.authenticated = False
        self._pending = {}
        self._connected_at = None
        self._voice_conv = []

    @property
    def is_connected(self):
        return self.laptop_connection is not None and self.authenticated

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
            await self.laptop_connection.send(json.dumps({
                "type": "cmd", "id": cmd_id,
                "action": action, "params": params or {},
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

    async def handle_voice_query(self, text):
        from .ai_handler import chat_with_ai, SYSTEM_PROMPT

        if not self._voice_conv:
            self._voice_conv = [{"role": "system", "content": SYSTEM_PROMPT}]

        self._voice_conv.append({"role": "user", "content": text})

        for _ in range(5):
            response = await chat_with_ai(self._voice_conv)
            if not response:
                return "AI service error. Check API key and configuration."

            choice = response["choices"][0]
            reply_msg = choice["message"]

            if reply_msg.get("tool_calls"):
                self._voice_conv.append(reply_msg)
                for tc in reply_msg["tool_calls"]:
                    if tc["type"] != "function":
                        continue
                    name = tc["function"]["name"]
                    try:
                        args = json.loads(tc["function"].get("arguments", "{}"))
                    except json.JSONDecodeError:
                        args = {}

                    action = AI_ACTION_MAP.get(name)
                    if not action:
                        self._voice_conv.append({
                            "role": "tool", "tool_call_id": tc["id"],
                            "name": name,
                            "content": json.dumps({"success": False, "error": f"Unknown: {name}"}),
                        })
                        continue

                    logger.info(f"Voice AI → laptop: {action}")
                    result = await self.send_command(action, args)
                    result_for_ai = dict(result)
                    if isinstance(result_for_ai.get("data"), str) and len(result_for_ai["data"]) > 1000:
                        result_for_ai["data"] = result_for_ai["data"][:1000] + "... [truncated]"
                    self._voice_conv.append({
                        "role": "tool", "tool_call_id": tc["id"],
                        "name": name,
                        "content": json.dumps(result_for_ai),
                    })
            else:
                reply = reply_msg.get("content", "")
                if reply:
                    self._voice_conv.append({"role": "assistant", "content": reply})
                return reply or "..."

        return "Maximum processing depth reached."

    async def handle_connection(self, websocket):
        logger.info("New WebSocket connection attempt")
        role = "agent"
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue

                t = data.get("type")

                if t == "auth":
                    if data.get("token") != AUTH_TOKEN:
                        await websocket.send(json.dumps({
                            "type": "auth_error", "error": "Invalid token",
                        }))
                        await websocket.close()
                        break

                    role = data.get("role", "agent")
                    if role == "voice":
                        self.voice_connection = websocket
                        await websocket.send(json.dumps({"type": "auth_ok", "role": "voice"}))
                        logger.info("Voice agent authenticated")
                    else:
                        self.laptop_connection = websocket
                        self.authenticated = True
                        self._connected_at = datetime.now()
                        await websocket.send(json.dumps({"type": "auth_ok", "role": "agent"}))
                        logger.info("Laptop agent authenticated successfully")

                elif t == "voice_query":
                    query_text = data.get("text", "")
                    if not query_text:
                        await websocket.send(json.dumps({
                            "type": "voice_response", "text": "No speech detected.",
                        }))
                        continue

                    logger.info(f"Voice query ({len(query_text)} chars): {query_text[:200]}")
                    response_text = await self.handle_voice_query(query_text)
                    logger.info(f"Voice response ({len(response_text)} chars): {response_text[:200]}")
                    await websocket.send(json.dumps({
                        "type": "voice_response", "text": response_text,
                    }))

                elif t == "result":
                    self.resolve(data.get("id"), data)

                elif t == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))

        except Exception as e:
            logger.warning(f"WebSocket ({role}) disconnected: {e}")
        finally:
            if role == "voice" and self.voice_connection == websocket:
                self.voice_connection = None
                logger.info("Voice agent cleaned up")
            elif self.laptop_connection == websocket:
                self.laptop_connection = None
                self.authenticated = False
                self._connected_at = None
                for cid, fut in self._pending.items():
                    if not fut.done():
                        fut.set_result({"success": False, "error": "Agent disconnected"})
                self._pending.clear()
                self._voice_conv = []
                logger.info("Laptop agent cleaned up")


manager = LaptopAgentManager()


async def health_check(connection, request):
    if request.path in ("/", "/health"):
        upgrade = request.headers.get("Upgrade", "")
        if upgrade.lower() == "websocket":
            return None
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
