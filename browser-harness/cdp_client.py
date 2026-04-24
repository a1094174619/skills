"""
Simple CDP (Chrome DevTools Protocol) client for Python 3.8+
Compatible with Python 3.8.10 and Windows 7
"""
import asyncio
import json
import logging
import sys
from typing import Any, Callable, Dict, Optional


if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


logger = logging.getLogger(__name__)


class CDPError(Exception):
    """
    CDP 协议错误
    
    当 CDP 命令返回错误时抛出
    """
    pass


class ConnectionError(Exception):
    """
    连接错误
    
    当 WebSocket 连接失败时抛出
    """
    pass


class EventRegistry:
    """
    CDP 事件注册表
    
    管理事件处理器和事件队列
    """
    
    def __init__(self) -> None:
        """初始化事件注册表"""
        self._handlers: Dict[str, Callable] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
    
    def on(self, event: str, handler: Callable) -> None:
        """
        注册事件处理器
        
        Args:
            event: 事件名称
            handler: 处理函数
        """
        self._handlers[event] = handler
        logger.debug("注册事件处理器: %s", event)
    
    async def handle_event(
        self,
        method: str,
        params: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Any:
        """
        处理事件
        
        Args:
            method: 事件方法名
            params: 事件参数
            session_id: 会话 ID
        
        Returns:
            处理器返回值（如果有）
        """
        if method in self._handlers:
            return await self._handlers[method](params, session_id)
        await self._event_queue.put({
            "method": method,
            "params": params,
            "session_id": session_id
        })
    
    async def get_event(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        从队列获取事件
        
        Args:
            timeout: 超时时间（秒）
        
        Returns:
            事件字典，超时返回 None
        """
        try:
            return await asyncio.wait_for(self._event_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


class CDPClient:
    """
    CDP 客户端
    
    通过 WebSocket 与 Chrome DevTools Protocol 通信
    """
    
    def __init__(self, ws_url: str) -> None:
        """
        初始化 CDP 客户端
        
        Args:
            ws_url: WebSocket URL
        """
        self.ws_url = ws_url
        self._ws = None
        self._msg_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._event_registry = EventRegistry()
        self._reader_task = None
        self._closed = False
    
    async def start(self, timeout: float = 30.0) -> None:
        """
        启动 CDP 客户端
        
        Args:
            timeout: 连接超时时间（秒）
        
        Raises:
            ConnectionError: 连接失败
        """
        import websockets.client
        
        logger.info("连接到 CDP: %s", self.ws_url)
        
        try:
            self._ws = await asyncio.wait_for(
                websockets.client.connect(self.ws_url, max_size=100 * 1024 * 1024),
                timeout=timeout
            )
            self._reader_task = asyncio.create_task(self._reader_loop())
            logger.info("CDP 客户端启动成功")
        except asyncio.TimeoutError:
            raise ConnectionError("连接超时 ({}秒)".format(timeout))
        except Exception as e:
            raise ConnectionError("连接失败: {}".format(e))
    
    async def close(self) -> None:
        """关闭 CDP 客户端"""
        self._closed = True
        logger.info("关闭 CDP 客户端")
        
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        
        if self._ws:
            await self._ws.close()
    
    async def _reader_loop(self) -> None:
        """读取 WebSocket 消息的循环"""
        try:
            async for message in self._ws:
                data = json.loads(message)
                
                if "id" in data:
                    future = self._pending.pop(data["id"], None)
                    if future and not future.done():
                        if "error" in data:
                            error = data["error"]
                            if isinstance(error, dict):
                                error_msg = error.get("message", str(error))
                            else:
                                error_msg = str(error)
                            future.set_exception(CDPError(error_msg))
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
            logger.error("读取循环错误: %s", e)
            if not self._closed:
                for future in self._pending.values():
                    if not future.done():
                        future.set_exception(e)
    
    async def send_raw(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        timeout: float = 30.0
    ) -> Any:
        """
        发送 CDP 命令
        
        Args:
            method: CDP 方法名
            params: 方法参数
            session_id: 会话 ID
            timeout: 超时时间（秒）
        
        Returns:
            命令结果
        
        Raises:
            CDPError: CDP 命令错误
            ConnectionError: 连接未建立
            asyncio.TimeoutError: 命令超时
        """
        if self._ws is None:
            raise ConnectionError("CDP 客户端未启动")
        
        self._msg_id += 1
        msg_id = self._msg_id
        
        msg = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        if session_id:
            msg["sessionId"] = session_id
        
        future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future
        
        logger.debug("发送 CDP: %s (id=%d)", method, msg_id)
        
        await self._ws.send(json.dumps(msg))
        
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            logger.debug("CDP 结果: %s", str(result)[:100])
            return result
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            logger.error("CDP 命令超时: %s (id=%d)", method, msg_id)
            raise
    
    @property
    def event_registry(self) -> EventRegistry:
        """
        获取事件注册表
        
        Returns:
            EventRegistry 实例
        """
        return self._event_registry
