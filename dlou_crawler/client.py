import re
import threading
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit, urljoin, urlunsplit
from urllib.error import URLError, HTTPError


class _SmartRedirect(HTTPRedirectHandler):
    max_redirects = 5

    def __init__(self) -> None:
        super().__init__()
        self._count = 0

    def reset(self) -> None:
        self._count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if self._count >= self.max_redirects:
            return None
        self._count += 1

        old = urlsplit(req.full_url)
        new = urlsplit(urljoin(req.full_url, newurl))

        if "cas/login" in new.path or "portal.dlou.edu.cn" in (new.hostname or ""):
            return None

        # 必须用 hostname（不含 userinfo/端口），避免 netloc 拆错或端口误伤
        old_host = (old.hostname or "").lower()
        new_host = (new.hostname or "").lower()
        if not old_host or not new_host:
            return None

        is_same_domain = (
            old_host == new_host
            or (old_host.endswith(".dlou.edu.cn") and new_host.endswith(".dlou.edu.cn"))
            or (old_host == "dlou.edu.cn" and new_host.endswith(".dlou.edu.cn"))
            or (new_host == "dlou.edu.cn" and old_host.endswith(".dlou.edu.cn"))
            or (old_host == "dlou.jysd.com" and new_host == "dlou.jysd.com")
        )

        is_https_upgrade = (
            old.scheme == "http"
            and new.scheme == "https"
            and old_host == new_host
        )

        if is_same_domain or is_https_upgrade:
            # 继承原请求头，避免重定向后丢失 UA/Accept 等
            new_req = Request(
                urlunsplit((new.scheme, new.netloc, new.path, new.query, new.fragment)),
                headers={k: v for k, v in req.headers.items()},
                origin_req_host=req.origin_req_host,
            )
            return new_req

        return None


# 允许访问的主机：dlou.edu.cn 子域 + 官网链接的官方就业网
ALLOWED_HOSTS = (
    "dlou.edu.cn",
    "dlou.jysd.com",  # 官网「人才培养→本科生就业」官方就业信息网
)


def _host_allowed(host: str) -> bool:
    host = (host or "").lower().split(":")[0]
    if not host:
        return False
    if host in ALLOWED_HOSTS:
        return True
    return any(host.endswith("." + h) for h in ALLOWED_HOSTS)


def is_allowed_url(url: str) -> bool:
    """http/https 且主机在白名单内。供图片预览等独立下载复用。"""
    if not url or not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url.strip())
    except Exception:
        return False
    scheme = (parts.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False
    # hostname：不含端口、不含 userinfo，避免 dlou.edu.cn:80@evil.com 类绕过
    return _host_allowed(parts.hostname or "")


def _charset_from_content_type(content_type: str) -> str:
    if not content_type:
        return ""
    m = re.search(r"charset\s*=\s*['\"]?([\w.-]+)", content_type, re.I)
    return m.group(1).strip() if m else ""


def _charset_from_meta(head: bytes) -> str:
    """从 HTML 头部猜 <meta charset=...> / content-type 声明。"""
    try:
        sample = head.decode("ascii", errors="ignore")
    except Exception:
        return ""
    m = re.search(r'charset\s*=\s*["\']?([\w.-]+)', sample, re.I)
    return m.group(1).strip() if m else ""


class HttpClient:
    # 单页响应上限，防超大页面把内存吃光
    MAX_RESPONSE_BYTES = 5 * 1024 * 1024

    def __init__(self, timeout: int = 15) -> None:
        self._timeout = timeout
        self._local = threading.local()

    def _get_opener(self):
        if not hasattr(self._local, "opener"):
            self._local.handler = _SmartRedirect()
            self._local.opener = build_opener(self._local.handler)
        return self._local.opener

    def get(self, url: str, retries: int = 3) -> str:
        """GET 文本响应；非白名单主机返回空串，登录墙返回空串，失败重试。"""
        if not url:
            return ""

        parsed = urlsplit(url)
        if not _host_allowed(parsed.hostname or ""):
            return ""

        opener = self._get_opener()

        for attempt in range(retries + 1):
            try:
                # 每次请求重置重定向计数，避免跨请求累积
                if hasattr(self._local, "handler"):
                    self._local.handler.reset()

                req = Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                                      "Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9",
                        "Connection": "keep-alive",
                    },
                )
                with opener.open(req, timeout=self._timeout) as resp:
                    raw = resp.read(self.MAX_RESPONSE_BYTES + 1)
                    if not raw:
                        continue
                    if len(raw) > self.MAX_RESPONSE_BYTES:
                        raw = raw[: self.MAX_RESPONSE_BYTES]

                    content_type = resp.headers.get("Content-Type", "")
                    text = ""
                    enc = _charset_from_content_type(content_type)
                    if enc:
                        try:
                            text = raw.decode(enc)
                        except (UnicodeDecodeError, LookupError):
                            text = ""
                    if not text:
                        enc = _charset_from_meta(raw[:2048])
                        if enc:
                            try:
                                text = raw.decode(enc)
                            except (UnicodeDecodeError, LookupError):
                                text = ""

                    if not text:
                        for enc in ("utf-8", "gbk", "gb2312"):
                            try:
                                text = raw.decode(enc)
                                break
                            except UnicodeDecodeError:
                                continue
                        if not text:
                            text = raw.decode("utf-8", errors="ignore")

                    # 统一身份认证 / 登录墙 / 校内 IP 墙：返回空串，由上层保留索引
                    head = text[:3000]
                    if is_blocked_page(head):
                        return ""
                    return text
            except HTTPError as e:
                # 4xx（除 429）不重试，避免死链反复打校内站
                code = getattr(e, "code", 0) or 0
                if 400 <= code < 500 and code != 429:
                    return ""
                if attempt < retries:
                    try:
                        import time
                        time.sleep(0.35 * (attempt + 1))
                    except Exception:
                        pass
                continue
            except (URLError, TimeoutError, OSError):
                # 简单退避，减轻对校内站压力
                if attempt < retries:
                    try:
                        import time
                        time.sleep(0.35 * (attempt + 1))
                    except Exception:
                        pass
                continue

        return ""


def is_blocked_page(text: str) -> bool:
    """是否登录墙 / 校内 IP 限制页（只看前部文案，避免误伤正常正文）。"""
    head = (text or "")[:3000]
    low = head.lower()
    if "统一身份认证" in head or "cas/login" in low or "login_type=" in low:
        return True
    # 只用「限制提示」原句，不用「校园网内」等易误伤的宽词
    if any(
        k in head
        for k in (
            "并非校内地址",
            "仅允许校内地址",
            "仅允许校内网访问",
            "校外不能访问",
            "非校内网不能",
            "该信息仅允许校内",
        )
    ):
        return True
    return False


def fetch_bytes(url: str, timeout: int = 15, max_bytes: int = 8 * 1024 * 1024) -> bytes:
    """白名单主机下载二进制；重定向同样限制主机（供图片预览用）。"""
    if not is_allowed_url(url):
        return b""
    handler = _SmartRedirect()
    opener = build_opener(handler)
    try:
        handler.reset()
        req = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; DLOUCrawler/1.0)",
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            },
        )
        with opener.open(req, timeout=timeout) as resp:
            final = getattr(resp, "url", url) or url
            if not is_allowed_url(final):
                return b""
            data = resp.read(max_bytes + 1)
            return data[:max_bytes]
    except Exception:
        return b""
