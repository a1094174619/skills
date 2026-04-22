"""
Simple CDP (Chrome DevTools Protocol) client for Python 3.8+
Compatible with Python 3.8.10 and Windows 7
"""
import asyncio
import json
from typing import Any, Dict, Optional, Callable


class CDPError(Exception):
    pass


class EventRegistry:
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()

    def on(self, event: str, handler: Callable):
        self._handlers[event] = handler

    async def handle_event(self, method: str, params: Dict, session_id: Optional[str] = None):
        if method in self._handlers:
            return await self._handlers[method](params, session_id)
        await self._event_queue.put({"method": method, "params": params, "session_id": session_id})

    async def get_event(self, timeout: float = 1.0):
        try:
            return await asyncio.wait_for(self._event_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class CDPClient:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self._ws = None
        self._msg_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._event_registry = EventRegistry()
        self._reader_task = None
        self._closed = False

    async def start(self):
        import websockets.client
        self._ws = await websockets.client.connect(self.ws_url, max_size=100 * 1024 * 1024)
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def close(self):
        self._closed = True
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()

    async def _reader_loop(self):
        try:
            async for message in self._ws:
                data = json.loads(message)
                if "id" in data:
                    future = self._pending.pop(data["id"], None)
                    if future and not future.done():
                        if "error" in data:
                            future.set_exception(CDPError(data["error"]))
                        else:
                            future.set_result(data.get("result"))
                else:
                    method = data.get("method", "")
                    params = data.get("params", {})
                    session_id = data.get("sessionId")
                    await self._event_registry.handle_event(method, params, session_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not self._closed:
                for future in self._pending.values():
                    if not future.done():
                        future.set_exception(e)

    async def send_raw(self, method: str, params: Optional[Dict] = None, session_id: Optional[str] = None) -> Any:
        if self._ws is None:
            raise CDPError("CDP client not started")
        
        self._msg_id += 1
        msg_id = self._msg_id
        
        msg = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        if session_id:
            msg["sessionId"] = session_id
        
        future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future
        
        await self._ws.send(json.dumps(msg))
        
        return await future

    @property
    def event_registry(self):
        return self._event_registry
