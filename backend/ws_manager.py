"""
Manages the persistent WebSocket connection from the laptop agent.
Only one laptop agent is expected to be connected at a time.
"""
import asyncio
import json
import logging
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WSManager:
    def __init__(self):
        self._socket: Optional[WebSocket] = None
        self._lock = asyncio.Lock()
        # pending futures keyed by a request id
        self._pending: dict[str, asyncio.Future] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            if self._socket is not None:
                # Disconnect old agent before accepting new one
                try:
                    await self._socket.close()
                except Exception:
                    pass
            self._socket = websocket
        logger.info("Laptop agent connected")

    def disconnect(self, websocket: WebSocket) -> None:
        if self._socket is websocket:
            self._socket = None
            logger.info("Laptop agent disconnected")

    @property
    def is_connected(self) -> bool:
        return self._socket is not None

    async def send_command(self, command: dict, wa_id: str, timeout: float = 30.0) -> dict:
        """
        Send a command to the laptop agent and await its result.
        Raises RuntimeError if the agent is not connected or times out.
        """
        if not self.is_connected:
            raise RuntimeError("Laptop agent is not connected")

        request_id = f"{wa_id}-{asyncio.get_event_loop().time():.4f}"
        command["_request_id"] = request_id
        command["_wa_id"] = wa_id

        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[request_id] = fut

        try:
            await self._socket.send_json(command)
            result = await asyncio.wait_for(fut, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            raise RuntimeError("Laptop agent did not respond in time")
        finally:
            self._pending.pop(request_id, None)

    async def receive_result(self, raw: str) -> None:
        """Called when the laptop agent sends a result back."""
        try:
            data = json.loads(raw)
            request_id = data.get("_request_id")
            if request_id and request_id in self._pending:
                self._pending[request_id].set_result(data)
        except Exception as e:
            logger.error(f"Error parsing agent result: {e}")
