"""
CDP WS holder + socket relay. One daemon per BU_NAME.

Compatible with Python 3.8.8+ and Windows 7+
"""
import asyncio
import hashlib
import json
import logging
import os
import platform
import socket
import ssl
import sys
import tempfile
import time
import urllib.request
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cdp_client import CDPClient


# ============================================================
# 日志配置
# ============================================================
logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    """
    配置日志级别
    
    Args:
        level: 日志级别，默认 INFO
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


# ============================================================
# 内部工具函数
# ============================================================
def _stable_hash(s: str) -> int:
    """
    生成稳定的哈希值（跨 Python 版本一致）
    
    Args:
        s: 输入字符串
    
    Returns:
        整数哈希值
    """
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


def _load_env() -> None:
    """从 .env 文件加载环境变量"""
    p = Path(__file__).parent / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

# ============================================================
# 全局配置
# ============================================================
NAME = os.environ.get("BU_NAME", "default")
IS_WINDOWS = platform.system() == "Windows"
TEMP_DIR = tempfile.gettempdir()

if IS_WINDOWS:
    SOCK_HOST = "127.0.0.1"
    SOCK_PORT = 9223 + _stable_hash(NAME) % 10000
    SOCK = (SOCK_HOST, SOCK_PORT)
    SOCK_PATH = os.path.join(TEMP_DIR, "bu-{}.port".format(NAME))
else:
    SOCK = "/tmp/bu-{}.sock".format(NAME)
    SOCK_PATH = SOCK

LOG = os.path.join(TEMP_DIR, "bu-{}.log".format(NAME))
PID = os.path.join(TEMP_DIR, "bu-{}.pid".format(NAME))
BUF = 500

# 浏览器配置文件路径
PROFILES = [
    Path.home() / "Library/Application Support/Google/Chrome",
    Path.home() / "Library/Application Support/Microsoft Edge",
    Path.home() / "Library/Application Support/Microsoft Edge Beta",
    Path.home() / "Library/Application Support/Microsoft Edge Dev",
    Path.home() / "Library/Application Support/Microsoft Edge Canary",
    Path.home() / ".config/google-chrome",
    Path.home() / ".config/chromium",
    Path.home() / ".config/chromium-browser",
    Path.home() / ".config/microsoft-edge",
    Path.home() / ".config/microsoft-edge-beta",
    Path.home() / ".config/microsoft-edge-dev",
    Path.home() / ".var/app/org.chromium.Chromium/config/chromium",
    Path.home() / ".var/app/com.google.Chrome/config/google-chrome",
    Path.home() / ".var/app/com.brave.Browser/config/BraveSoftware/Brave-Browser",
    Path.home() / ".var/app/com.microsoft.Edge/config/microsoft-edge",
    Path.home() / "AppData/Local/Google/Chrome/User Data",
    Path.home() / "AppData/Local/Chromium/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge Beta/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge Dev/User Data",
    Path.home() / "AppData/Local/Microsoft/Edge SxS/User Data",
]

INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")
BU_API = "https://api.browser-use.com/api/v3"
REMOTE_ID = os.environ.get("BU_BROWSER_ID")
API_KEY = os.environ.get("BROWSER_USE_API_KEY")

# 超时配置
DEFAULT_TIMEOUT = 30.0
ENABLE_TIMEOUT = 5.0


# ============================================================
# 异常类
# ============================================================
class DaemonError(Exception):
    """Daemon 错误"""
    pass


class ConnectionError(DaemonError):
    """连接错误"""
    pass


# ============================================================
# 日志函数
# ============================================================
def log(msg: str) -> None:
    """
    写入日志文件
    
    Args:
        msg: 日志消息
    """
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("{}\n".format(msg))


# ============================================================
# WebSocket URL 获取
# ============================================================
def get_ws_url() -> str:
    """
    获取 CDP WebSocket URL
    
    Returns:
        WebSocket URL
    
    Raises:
        RuntimeError: 无法找到 DevToolsActivePort 文件
    """
    url = os.environ.get("BU_CDP_WS")
    if url:
        logger.info("使用环境变量 BU_CDP_WS: %s", url)
        return url
    
    for base in PROFILES:
        try:
            port_path = base / "DevToolsActivePort"
            content = port_path.read_text().strip()
            lines = content.split("\n", 1)
            if len(lines) < 2:
                continue
            port, path = lines[0].strip(), lines[1].strip()
        except (FileNotFoundError, NotADirectoryError):
            continue
        
        deadline = time.time() + DEFAULT_TIMEOUT
        while True:
            probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            probe.settimeout(1)
            try:
                probe.connect(("127.0.0.1", int(port)))
                probe.close()
                break
            except OSError:
                probe.close()
                if time.time() >= deadline:
                    raise RuntimeError(
                        "Chrome's remote-debugging page is open, but DevTools is not live yet on 127.0.0.1:{} -- if Chrome opened a profile picker, choose your normal profile first, then tick the checkbox and click Allow if shown".format(port)
                    )
                time.sleep(1)
        
        ws_url = "ws://127.0.0.1:{}{}".format(port, path)
        logger.info("找到 DevToolsActivePort: %s", ws_url)
        return ws_url
    
    raise RuntimeError(
        "DevToolsActivePort not found in {} -- enable chrome://inspect/#remote-debugging, or set BU_CDP_WS for a remote browser".format(
            [str(p) for p in PROFILES]
        )
    )


# ============================================================
# 远程浏览器管理
# ============================================================
def stop_remote() -> None:
    """停止远程浏览器（如果使用）"""
    if not REMOTE_ID or not API_KEY:
        return
    
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        
        req = urllib.request.Request(
            "{}/browsers/{}".format(BU_API, REMOTE_ID),
            data=json.dumps({"action": "stop"}).encode(),
            method="PATCH",
            headers={"X-Browser-Use-API-Key": API_KEY, "Content-Type": "application/json"},
        )
        
        urllib.request.urlopen(req, timeout=15, context=ctx).read()
        log("stopped remote browser {}".format(REMOTE_ID))
        logger.info("已停止远程浏览器: %s", REMOTE_ID)
    
    except Exception as e:
        log("stop_remote failed ({}): {}".format(REMOTE_ID, e))
        logger.warning("停止远程浏览器失败: %s", e)


def is_real_page(t: Dict[str, Any]) -> bool:
    """
    检查是否为真实页面（非内部页面）
    
    Args:
        t: 目标信息字典
    
    Returns:
        是否为真实页面
    """
    return t.get("type") == "page" and not t.get("url", "").startswith(INTERNAL)


# ============================================================
# Daemon 类
# ============================================================
class Daemon:
    """
    CDP WebSocket 守护进程
    
    管理 CDP 连接、会话和事件处理
    """
    
    def __init__(self) -> None:
        """初始化 Daemon"""
        self.cdp = None
        self.session = None
        self.events = deque(maxlen=BUF)
        self.dialog = None
        self.stop = None
    
    async def attach_first_page(self) -> Optional[Dict[str, Any]]:
        """
        附加到第一个真实页面
        
        Returns:
            页面信息字典，如果没有真实页面则返回 None
        """
        targets = (await self.cdp.send_raw("Target.getTargets")).get("targetInfos", [])
        pages = [t for t in targets if is_real_page(t)]
        
        if not pages:
            tid = (await self.cdp.send_raw("Target.createTarget", {"url": "about:blank"})).get("targetId", "")
            log("no real pages found, created about:blank ({})".format(tid))
            pages = [{"targetId": tid, "url": "about:blank", "type": "page"}]
        
        page = pages[0]
        self.session = (await self.cdp.send_raw(
            "Target.attachToTarget", {"targetId": page["targetId"], "flatten": True}
        )).get("sessionId", "")
        
        log("attached {} ({}) session={}".format(
            page["targetId"],
            page.get("url", "")[:80],
            self.session
        ))
        
        for domain in ("Page", "DOM", "Runtime", "Network"):
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw("{}.enable".format(domain), session_id=self.session),
                    timeout=ENABLE_TIMEOUT
                )
            except asyncio.TimeoutError:
                log("enable {} timeout".format(domain))
                logger.warning("启用 %s 超时", domain)
            except Exception as e:
                log("enable {}: {}".format(domain, e))
                logger.warning("启用 %s 失败: %s", domain, e)
        
        return page
    
    async def start(self) -> None:
        """启动 Daemon"""
        self.stop = asyncio.Event()
        url = get_ws_url()
        log("connecting to {}".format(url))
        logger.info("连接到: %s", url)
        
        self.cdp = CDPClient(url)
        
        try:
            await self.cdp.start()
        except Exception as e:
            raise RuntimeError(
                "CDP WS handshake failed: {} -- click Allow in Chrome if prompted, then retry".format(e)
            )
        
        await self.attach_first_page()
        
        orig = self.cdp.event_registry.handle_event
        mark_js = "if(!document.title.startsWith('\\U0001F7E2'))document.title='\\U0001F7E2 '+document.title"
        
        async def tap(method: str, params: Dict[str, Any], session_id: Optional[str] = None) -> Any:
            """事件处理钩子"""
            self.events.append({"method": method, "params": params, "session_id": session_id})
            
            if method == "Page.javascriptDialogOpening":
                self.dialog = params
            elif method == "Page.javascriptDialogClosed":
                self.dialog = None
            elif method in ("Page.loadEventFired", "Page.domContentEventFired"):
                try:
                    await asyncio.wait_for(
                        self.cdp.send_raw("Runtime.evaluate", {"expression": mark_js}, session_id=self.session),
                        timeout=2
                    )
                except Exception:
                    pass
            
            return await orig(method, params, session_id)
        
        self.cdp.event_registry.handle_event = tap
        logger.info("Daemon 启动成功")
    
    async def handle(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理客户端请求
        
        Args:
            req: 请求字典
        
        Returns:
            响应字典
        """
        meta = req.get("meta")
        
        if meta == "drain_events":
            out = list(self.events)
            self.events.clear()
            return {"events": out}
        
        if meta == "session":
            return {"session_id": self.session}
        
        if meta == "set_session":
            self.session = req.get("session_id")
            try:
                await asyncio.wait_for(
                    self.cdp.send_raw("Page.enable", session_id=self.session),
                    timeout=3
                )
                await asyncio.wait_for(
                    self.cdp.send_raw(
                        "Runtime.evaluate",
                        {"expression": "if(!document.title.startsWith('\\U0001F7E2'))document.title='\\U0001F7E2 '+document.title"},
                        session_id=self.session
                    ),
                    timeout=2
                )
            except Exception:
                pass
            return {"session_id": self.session}
        
        if meta == "pending_dialog":
            return {"dialog": self.dialog}
        
        if meta == "shutdown":
            self.stop.set()
            return {"ok": True}
        
        method = req.get("method", "")
        params = req.get("params") or {}
        sid = None if method.startswith("Target.") else (req.get("session_id") or self.session)
        
        try:
            return {"result": await self.cdp.send_raw(method, params, session_id=sid)}
        except Exception as e:
            msg = str(e)
            if "Session with given id not found" in msg and sid == self.session and sid:
                log("stale session {}, re-attaching".format(sid))
                logger.warning("会话过期，重新附加: %s", sid)
                if await self.attach_first_page():
                    return {"result": await self.cdp.send_raw(method, params, session_id=self.session)}
            return {"error": msg}


# ============================================================
# 服务器
# ============================================================
async def serve(d: Daemon) -> None:
    """
    启动服务器
    
    Args:
        d: Daemon 实例
    """
    async def handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """处理客户端连接"""
        try:
            line = await reader.readline()
            if not line:
                return
            
            resp = await d.handle(json.loads(line))
            writer.write((json.dumps(resp, default=str) + "\n").encode())
            await writer.drain()
        
        except Exception as e:
            log("conn: {}".format(e))
            logger.error("连接错误: %s", e)
            try:
                writer.write((json.dumps({"error": str(e)}) + "\n").encode())
                await writer.drain()
            except Exception:
                pass
        
        finally:
            writer.close()
    
    if IS_WINDOWS:
        server = await asyncio.start_server(handler, host=SOCK_HOST, port=SOCK_PORT)
        with open(SOCK_PATH, "w") as f:
            f.write(str(SOCK_PORT))
        log("listening on {}:{} (name={}, remote={})".format(SOCK_HOST, SOCK_PORT, NAME, REMOTE_ID or 'local'))
        logger.info("监听 %s:%s (name=%s, remote=%s)", SOCK_HOST, SOCK_PORT, NAME, REMOTE_ID or 'local')
    else:
        if os.path.exists(SOCK):
            os.unlink(SOCK)
        server = await asyncio.start_unix_server(handler, path=SOCK)
        os.chmod(SOCK, 0o600)
        log("listening on {} (name={}, remote={})".format(SOCK, NAME, REMOTE_ID or 'local'))
        logger.info("监听 %s (name=%s, remote=%s)", SOCK, NAME, REMOTE_ID or 'local')
    
    async with server:
        await d.stop.wait()


async def main() -> None:
    """主函数"""
    d = Daemon()
    await d.start()
    await serve(d)


def already_running() -> bool:
    """
    检查是否已有 Daemon 在运行
    
    Returns:
        是否已有 Daemon 在运行
    """
    try:
        if IS_WINDOWS:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((SOCK_HOST, SOCK_PORT))
            s.close()
            return True
        else:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(SOCK)
            s.close()
            return True
    except (FileNotFoundError, ConnectionRefusedError, socket.timeout, OSError):
        return False


if __name__ == "__main__":
    if already_running():
        if IS_WINDOWS:
            print("daemon already running on {}:{}".format(SOCK_HOST, SOCK_PORT), file=sys.stderr)
        else:
            print("daemon already running on {}".format(SOCK), file=sys.stderr)
        sys.exit(0)
    
    with open(LOG, "w", encoding="utf-8") as f:
        pass
    
    with open(PID, "w") as f:
        f.write(str(os.getpid()))
    
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    except Exception as e:
        log("fatal: {}".format(e))
        logger.error("致命错误: %s", e)
        sys.exit(1)
    finally:
        stop_remote()
        try:
            os.unlink(PID)
        except FileNotFoundError:
            pass
        if IS_WINDOWS:
            try:
                os.unlink(SOCK_PATH)
            except FileNotFoundError:
                pass
