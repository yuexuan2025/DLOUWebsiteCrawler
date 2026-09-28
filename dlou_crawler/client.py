import threading
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit, urljoin, urlunsplit
from urllib.error import URLError, HTTPError


class _SmartRedirect(HTTPRedirectHandler):
    max_redirects = 3

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

        if "cas/login" in new.path or "portal.dlou.edu.cn" in new.netloc:
            return None

        old_host = old.netloc.lower()
        new_host = new.netloc.lower()
        is_same_domain = (
            old_host == new_host
            or (old_host.endswith(".dlou.edu.cn") and new_host.endswith(".dlou.edu.cn"))
            or (old_host == "dlou.edu.cn" and new_host.endswith(".dlou.edu.cn"))
            or (new_host.endswith(".dlou.edu.cn") and old_host.endswith(".dlou.edu.cn"))
            or (old_host == "dlou.jysd.com" and new_host == "dlou.jysd.com")
        )

        is_https_upgrade = (
            old.scheme == "http"
            and new.scheme == "https"
            and old_host == new_host
        )

        if is_same_domain or is_https_upgrade:
            ua = req.get_header("User-Agent") or "Mozilla/5.0"
            new_req = Request(
                urlunsplit(new),
                headers={"User-Agent": ua},
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


class HttpClient:
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
        host = parsed.netloc.lower()
        if not _host_allowed(host):
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
                    raw = resp.read()
                    if not raw:
                        continue

                    content_type = resp.headers.get("Content-Type", "")
                    text = ""
                    if "charset=" in content_type:
                        enc = content_type.split("charset=")[-1].strip()
                        try:
                            text = raw.decode(enc)
                        except (UnicodeDecodeError, LookupError):
                            text = ""

                    if not text:
                        for enc in ("utf-8", "gbk", "gb2312", "iso-8859-1"):
                            try:
                                text = raw.decode(enc)
                                break
                            except UnicodeDecodeError:
                                continue
                        if not text:
                            text = raw.decode("utf-8", errors="ignore")

                    # 统一身份认证 / 登录墙：直接放弃，避免伪正文
                    head = text[:2000]
                    if "统一身份认证" in head or "cas/login" in head.lower() or "login_type=" in head.lower():
                        return ""
                    return text
            except (URLError, HTTPError, TimeoutError, OSError):
                continue

        return ""
