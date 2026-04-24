"""
Browser control via CDP. Read, edit, extend -- this file is yours.

Compatible with Python 3.8.8+ and Windows 7+
"""
import base64
import functools
import gzip
import hashlib
import json
import logging
import os
import platform
import re
import socket
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from urllib.parse import urlparse


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
else:
    SOCK = "/tmp/bu-{}.sock".format(NAME)

INTERNAL = ("chrome://", "chrome-untrusted://", "devtools://", "chrome-extension://", "about:")

# 默认超时时间（秒）
DEFAULT_TIMEOUT = 30.0

# Chrome 版本缓存
_CHROME_VERSION = None


# ============================================================
# 异常类
# ============================================================
class BrowserHarnessError(Exception):
    """browser-harness 基础异常"""
    pass


class CDPError(BrowserHarnessError):
    """CDP 命令执行错误"""
    pass


class TimeoutError(BrowserHarnessError):
    """操作超时错误"""
    pass


class ConnectionError(BrowserHarnessError):
    """连接错误"""
    pass


# ============================================================
# Chrome 版本检测
# ============================================================
def get_chrome_version() -> int:
    """
    获取 Chrome 主版本号
    
    Returns:
        Chrome 主版本号，如 109、147 等。获取失败返回 0。
    """
    global _CHROME_VERSION
    if _CHROME_VERSION is None:
        try:
            info = cdp("Browser.getVersion", _internal=True)
            product = info.get("product", "")
            match = re.search(r"Chrome/(\d+)", product)
            _CHROME_VERSION = int(match.group(1)) if match else 0
            logger.debug("检测到 Chrome 版本: %d", _CHROME_VERSION)
        except Exception as e:
            logger.warning("无法获取 Chrome 版本: %s", e)
            _CHROME_VERSION = 0
    return _CHROME_VERSION


# ============================================================
# 核心通信函数
# ============================================================
def _send(req: Dict[str, Any], timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """
    发送请求到 daemon 并接收响应
    
    Args:
        req: 请求字典
        timeout: 超时时间（秒）
    
    Returns:
        响应字典
    
    Raises:
        ConnectionError: 连接失败
        CDPError: CDP 命令错误
        TimeoutError: 操作超时
    """
    s = None
    try:
        if IS_WINDOWS:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(SOCK)
        else:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect(SOCK)
        
        s.sendall((json.dumps(req) + "\n").encode())
        
        data = b""
        while not data.endswith(b"\n"):
            chunk = s.recv(1 << 20)
            if not chunk:
                break
            data += chunk
        
        r = json.loads(data)
        
        if "error" in r:
            error_msg = r["error"]
            if isinstance(error_msg, dict):
                error_msg = error_msg.get("message", str(error_msg))
            raise CDPError("CDP 错误: {}".format(error_msg))
        
        return r
    
    except socket.timeout:
        raise TimeoutError("操作超时 ({}秒)".format(timeout))
    except socket.error as e:
        raise ConnectionError("连接失败: {}".format(e))
    finally:
        if s:
            s.close()


def cdp(
    method: str,
    session_id: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
    _internal: bool = False,
    **params: Any
) -> Dict[str, Any]:
    """
    执行 CDP (Chrome DevTools Protocol) 命令
    
    Args:
        method: CDP 方法名，如 "Page.navigate"
        session_id: 可选的会话 ID
        timeout: 超时时间（秒）
        _internal: 内部调用标志，跳过日志
        **params: CDP 方法参数
    
    Returns:
        CDP 命令结果
    
    Raises:
        CDPError: CDP 命令执行失败
        TimeoutError: 操作超时
        ConnectionError: 连接失败
    
    Example:
        >>> result = cdp("Browser.getVersion")
        >>> print(result.get("product"))
        Chrome/109.0.5414.129
    """
    if not _internal:
        logger.debug("CDP: %s %s", method, list(params.keys()))
    
    req = {"method": method, "params": params}
    if session_id:
        req["session_id"] = session_id
    
    result = _send(req, timeout=timeout).get("result", {})
    
    if not _internal:
        logger.debug("CDP 结果: %s", str(result)[:100])
    
    return result


def drain_events() -> List[Dict[str, Any]]:
    """
    获取并清空事件队列
    
    Returns:
        事件列表
    """
    return _send({"meta": "drain_events"})["events"]


# ============================================================
# 页面导航
# ============================================================
def _removeprefix(s: str, prefix: str) -> str:
    """移除字符串前缀（Python 3.8 兼容）"""
    return s[len(prefix):] if s.startswith(prefix) else s


def goto(url: str, timeout: float = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """
    导航到指定 URL
    
    Args:
        url: 目标 URL
        timeout: 超时时间（秒）
    
    Returns:
        导航结果，包含 domain_skills 字段（如果有）
    
    Raises:
        ValueError: URL 无效
        CDPError: 导航失败
    
    Example:
        >>> result = goto("https://www.baidu.com")
        >>> print(result.get("domain_skills", []))
    """
    if not url:
        raise ValueError("URL 不能为空")
    
    logger.info("导航到: %s", url)
    
    r = cdp("Page.navigate", url=url, timeout=timeout)
    
    hostname = urlparse(url).hostname or ""
    hostname = _removeprefix(hostname, "www.")
    d = Path(__file__).parent / "domain-skills" / hostname.split(".")[0]
    
    if d.is_dir():
        domain_skills = sorted(p.name for p in d.rglob("*.md"))[:10]
        return dict(r, domain_skills=domain_skills) if domain_skills else r
    
    return r


# ============================================================
# 页面信息
# ============================================================
def page_info() -> Dict[str, Any]:
    """
    获取当前页面信息
    
    Returns:
        包含 url, title, w, h, sx, sy, pw, ph 的字典
        如果有对话框，返回 {"dialog": dialog_type}
    
    Example:
        >>> info = page_info()
        >>> print(info["url"], info["title"])
    """
    dialog = _send({"meta": "pending_dialog"}).get("dialog")
    if dialog:
        return {"dialog": dialog}
    
    r = cdp(
        "Runtime.evaluate",
        expression="JSON.stringify({url:location.href,title:document.title,w:innerWidth,h:innerHeight,sx:scrollX,sy:scrollY,pw:document.documentElement.scrollWidth,ph:document.documentElement.scrollHeight})",
        returnByValue=True
    )
    
    result_value = r.get("result", {}).get("value", "{}")
    return json.loads(result_value)


# ============================================================
# 鼠标操作
# ============================================================
def click(
    x: Union[int, float],
    y: Union[int, float],
    button: str = "left",
    clicks: int = 1
) -> None:
    """
    在指定坐标点击
    
    Args:
        x: X 坐标
        y: Y 坐标
        button: 鼠标按钮，"left"、"right" 或 "middle"
        clicks: 点击次数
    
    Example:
        >>> click(500, 300)  # 单击
        >>> click(500, 300, clicks=2)  # 双击
    """
    logger.debug("点击: (%.0f, %.0f) %s x%d", x, y, button, clicks)
    
    cdp("Input.dispatchMouseEvent", type="mousePressed", x=x, y=y, button=button, clickCount=clicks)
    cdp("Input.dispatchMouseEvent", type="mouseReleased", x=x, y=y, button=button, clickCount=clicks)


def scroll(
    x: Union[int, float],
    y: Union[int, float],
    dy: int = -300,
    dx: int = 0
) -> None:
    """
    滚动页面
    
    Args:
        x: 鼠标 X 坐标
        y: 鼠标 Y 坐标
        dy: 垂直滚动距离，负值向上滚动
        dx: 水平滚动距离，负值向左滚动
    
    Example:
        >>> scroll(500, 300, dy=-500)  # 向上滚动
    """
    logger.debug("滚动: (%.0f, %.0f) delta=(%d, %d)", x, y, dx, dy)
    cdp("Input.dispatchMouseEvent", type="mouseWheel", x=x, y=y, deltaX=dx, deltaY=dy)


# ============================================================
# 键盘操作
# ============================================================
_KEYS = {
    "Enter": (13, "Enter", "\r"),
    "Tab": (9, "Tab", "\t"),
    "Backspace": (8, "Backspace", ""),
    "Escape": (27, "Escape", ""),
    "Delete": (46, "Delete", ""),
    " ": (32, "Space", " "),
    "ArrowLeft": (37, "ArrowLeft", ""),
    "ArrowUp": (38, "ArrowUp", ""),
    "ArrowRight": (39, "ArrowRight", ""),
    "ArrowDown": (40, "ArrowDown", ""),
    "Home": (36, "Home", ""),
    "End": (35, "End", ""),
    "PageUp": (33, "PageUp", ""),
    "PageDown": (34, "PageDown", ""),
}


def type_text(text: str) -> None:
    """
    输入文本
    
    Args:
        text: 要输入的文本
    
    Example:
        >>> type_text("Hello World")
        >>> type_text("中文测试")
    """
    if not text:
        return
    logger.debug("输入文本: %s", text[:50] + "..." if len(text) > 50 else text)
    cdp("Input.insertText", text=text)


def press_key(key: str, modifiers: int = 0) -> None:
    """
    按下并释放按键
    
    Args:
        key: 按键名称或字符，如 "Enter"、"Tab"、"a"
        modifiers: 修饰键位掩码 (Alt=1, Ctrl=2, Meta/Command=4, Shift=8)
    
    Example:
        >>> press_key("Enter")
        >>> press_key("a", modifiers=2)  # Ctrl+A
    """
    vk, code, text = _KEYS.get(
        key,
        (ord(key[0]) if len(key) == 1 else 0, key, key if len(key) == 1 else "")
    )
    
    base = {
        "key": key,
        "code": code,
        "modifiers": modifiers,
        "windowsVirtualKeyCode": vk,
        "nativeVirtualKeyCode": vk
    }
    
    logger.debug("按键: %s (modifiers=%d)", key, modifiers)
    
    cdp("Input.dispatchKeyEvent", type="keyDown", **base, **({"text": text} if text else {}))
    if text and len(text) == 1:
        cdp("Input.dispatchKeyEvent", type="char", text=text, **{k: v for k, v in base.items() if k != "text"})
    cdp("Input.dispatchKeyEvent", type="keyUp", **base)


# ============================================================
# 截图
# ============================================================
def screenshot(
    path: Optional[str] = None,
    full: bool = False,
    timeout: float = DEFAULT_TIMEOUT
) -> str:
    """
    截取当前页面截图
    
    Args:
        path: 截图保存路径，默认为临时目录下的 shot.png
        full: 是否截取完整页面（需要 Chrome 110+）
        timeout: 超时时间（秒）
    
    Returns:
        截图文件的绝对路径
    
    Raises:
        CDPError: 截图失败
    
    Example:
        >>> path = screenshot()
        >>> path = screenshot("/tmp/page.png", full=True)
    """
    if path is None:
        path = os.path.join(TEMP_DIR, "shot.png")
    
    params = {"format": "png"}
    
    # Chrome 110+ 才支持 captureBeyondViewport
    if full:
        chrome_version = get_chrome_version()
        if chrome_version >= 110:
            params["captureBeyondViewport"] = True
            logger.debug("启用 captureBeyondViewport (Chrome %d)", chrome_version)
        else:
            logger.warning("Chrome %d 不支持 captureBeyondViewport，将截取可视区域", chrome_version)
    
    logger.info("截图: %s", path)
    
    r = cdp("Page.captureScreenshot", timeout=timeout, **params)
    
    if not r or "data" not in r:
        raise CDPError("截图返回数据为空")
    
    with open(path, "wb") as f:
        f.write(base64.b64decode(r["data"]))
    
    logger.debug("截图大小: %d bytes", len(r["data"]))
    
    return path


# ============================================================
# 标签页管理
# ============================================================
def list_tabs(include_chrome: bool = True) -> List[Dict[str, str]]:
    """
    列出所有标签页
    
    Args:
        include_chrome: 是否包含 Chrome 内部页面（chrome://、about: 等）
    
    Returns:
        标签页列表，每个元素包含 targetId、title、url
    
    Example:
        >>> tabs = list_tabs()
        >>> for tab in tabs:
        ...     print(tab["title"], tab["url"])
    """
    out = []
    for t in cdp("Target.getTargets").get("targetInfos", []):
        if t.get("type") != "page":
            continue
        url = t.get("url", "")
        if not include_chrome and url.startswith(INTERNAL):
            continue
        out.append({
            "targetId": t.get("targetId", ""),
            "title": t.get("title", ""),
            "url": url
        })
    return out


def current_tab() -> Dict[str, str]:
    """
    获取当前标签页信息
    
    Returns:
        包含 targetId、url、title 的字典
    
    Example:
        >>> tab = current_tab()
        >>> print(tab["url"])
    """
    t = cdp("Target.getTargetInfo").get("targetInfo", {})
    return {
        "targetId": t.get("targetId", ""),
        "url": t.get("url", ""),
        "title": t.get("title", "")
    }


def _mark_tab() -> None:
    """标记当前标签页（添加绿色圆点前缀）"""
    try:
        cdp("Runtime.evaluate", expression="if(!document.title.startsWith('\\U0001F7E2'))document.title='\\U0001F7E2 '+document.title")
    except Exception:
        pass


def switch_tab(target_id: str) -> str:
    """
    切换到指定标签页
    
    Args:
        target_id: 目标标签页 ID
    
    Returns:
        新的会话 ID
    
    Example:
        >>> tabs = list_tabs()
        >>> session_id = switch_tab(tabs[0]["targetId"])
    """
    if not target_id:
        raise ValueError("target_id 不能为空")
    
    logger.info("切换标签页: %s", target_id[:20])
    
    try:
        cdp("Runtime.evaluate", expression="if(document.title.startsWith('\\U0001F7E2 '))document.title=document.title.slice(2)")
    except Exception:
        pass
    
    cdp("Target.activateTarget", targetId=target_id)
    
    sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True).get("sessionId", "")
    _send({"meta": "set_session", "session_id": sid})
    _mark_tab()
    
    return sid


def new_tab(url: str = "about:blank") -> str:
    """
    创建新标签页
    
    Args:
        url: 初始 URL，默认为 about:blank
    
    Returns:
        新标签页的 targetId
    
    Example:
        >>> tab_id = new_tab("https://www.baidu.com")
    """
    logger.info("新建标签页: %s", url)
    
    tid = cdp("Target.createTarget", url="about:blank").get("targetId", "")
    switch_tab(tid)
    
    if url != "about:blank":
        goto(url)
    
    return tid


def ensure_real_tab() -> Optional[Dict[str, str]]:
    """
    确保有一个真实的（非内部）标签页
    
    Returns:
        当前标签页信息，如果没有真实标签页则返回 None
    
    Example:
        >>> tab = ensure_real_tab()
        >>> if tab:
        ...     print("当前标签页:", tab["url"])
    """
    tabs = list_tabs(include_chrome=False)
    if not tabs:
        return None
    
    try:
        cur = current_tab()
        if cur.get("url") and not cur["url"].startswith(INTERNAL):
            return cur
    except Exception:
        pass
    
    switch_tab(tabs[0]["targetId"])
    return tabs[0]


def iframe_target(url_substr: str) -> Optional[str]:
    """
    查找包含指定 URL 子串的 iframe
    
    Args:
        url_substr: URL 子串
    
    Returns:
        iframe 的 targetId，未找到返回 None
    
    Example:
        >>> iframe_id = iframe_target("youtube.com")
    """
    for t in cdp("Target.getTargets").get("targetInfos", []):
        if t.get("type") == "iframe" and url_substr in t.get("url", ""):
            return t.get("targetId")
    return None


# ============================================================
# 等待和同步
# ============================================================
def wait(seconds: float = 1.0) -> None:
    """
    等待指定秒数
    
    Args:
        seconds: 等待时间（秒）
    
    Example:
        >>> wait(2)  # 等待 2 秒
    """
    time.sleep(seconds)


def wait_for_load(timeout: float = 15.0, poll_interval: float = 0.3) -> bool:
    """
    等待页面加载完成
    
    Args:
        timeout: 超时时间（秒）
        poll_interval: 轮询间隔（秒）
    
    Returns:
        是否在超时前加载完成
    
    Example:
        >>> if wait_for_load():
        ...     print("页面加载完成")
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if js("document.readyState") == "complete":
            return True
        time.sleep(poll_interval)
    return False


# ============================================================
# JavaScript 执行
# ============================================================
def js(expression: str, target_id: Optional[str] = None) -> Any:
    """
    执行 JavaScript 表达式
    
    Args:
        expression: JavaScript 表达式
        target_id: 可选的目标 ID（用于 iframe）
    
    Returns:
        表达式的返回值
    
    Example:
        >>> result = js("1 + 1")
        >>> print(result)  # 2
        >>> title = js("document.title")
    """
    sid = None
    if target_id:
        sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True).get("sessionId")
    
    r = cdp(
        "Runtime.evaluate",
        session_id=sid,
        expression=expression,
        returnByValue=True,
        awaitPromise=True
    )
    
    return r.get("result", {}).get("value")


# ============================================================
# 高级交互
# ============================================================
_KC = {
    "Enter": 13,
    "Tab": 9,
    "Escape": 27,
    "Backspace": 8,
    " ": 32,
    "ArrowLeft": 37,
    "ArrowUp": 38,
    "ArrowRight": 39,
    "ArrowDown": 40
}


def dispatch_key(selector: str, key: str = "Enter", event: str = "keypress") -> None:
    """
    向指定元素分发键盘事件
    
    Args:
        selector: CSS 选择器
        key: 按键名称
        event: 事件类型
    
    Example:
        >>> dispatch_key("#search-input", "Enter")
    """
    kc = _KC.get(key, ord(key) if len(key) == 1 else 0)
    js(
        "(()=>{{const e=document.querySelector({});if(e){{e.focus();e.dispatchEvent(new KeyboardEvent({},{{key:{},code:{},keyCode:{},which:{},bubbles:true}}));}}}})()".format(
            json.dumps(selector),
            json.dumps(event),
            json.dumps(key),
            json.dumps(key),
            kc,
            kc
        )
    )


def upload_file(selector: str, path: Union[str, List[str]]) -> None:
    """
    上传文件到文件输入框
    
    Args:
        selector: CSS 选择器
        path: 文件路径或路径列表
    
    Raises:
        RuntimeError: 找不到指定元素
    
    Example:
        >>> upload_file("#file-input", "/path/to/file.pdf")
    """
    doc = cdp("DOM.getDocument", depth=-1)
    nid = cdp("DOM.querySelector", nodeId=doc["root"]["nodeId"], selector=selector).get("nodeId")
    
    if not nid:
        raise RuntimeError("找不到元素: {}".format(selector))
    
    files = [path] if isinstance(path, str) else list(path)
    logger.info("上传文件: %s -> %s", files, selector)
    
    cdp("DOM.setFileInputFiles", files=files, nodeId=nid)


# ============================================================
# HTTP 请求
# ============================================================
def http_get(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 20.0
) -> str:
    """
    发送 HTTP GET 请求
    
    Args:
        url: 请求 URL
        headers: 额外的请求头
        timeout: 超时时间（秒）
    
    Returns:
        响应内容（文本）
    
    Example:
        >>> html = http_get("https://example.com")
    """
    h = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
    if headers:
        h.update(headers)
    
    logger.debug("HTTP GET: %s", url)
    
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data.decode()
