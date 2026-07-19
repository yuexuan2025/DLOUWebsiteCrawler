from __future__ import annotations

import time
import urllib.robotparser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


class FetchError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    """Do not follow redirects to login systems or other unexpected destinations."""

    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class PoliteClient:
    """HTTP client with robots checks and a deliberately modest request rate."""

    def __init__(self, user_agent: str, delay: float, timeout: int = 20) -> None:
        self.user_agent = user_agent
        self.delay = delay
        self.timeout = timeout
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_request = 0.0
        self._opener = build_opener(_NoRedirect())

    def can_fetch(self, url: str) -> bool:
        from urllib.parse import urlsplit

        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self._robots:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(root + "/robots.txt")
            try:
                self._wait()
                parser.read()
            except HTTPError as error:
                if error.code == 404:
                    # Per the robots exclusion protocol, a missing robots.txt means
                    # no rules have been published for this host.
                    parser.allow_all = True
                else:
                    return False
            except (OSError, URLError):
                # A missing robots file should not make the program guess it is allowed.
                return False
            self._robots[root] = parser
        return self._robots[root].can_fetch(self.user_agent, url)

    def get_text(self, url: str) -> str:
        response = self._open(url)
        charset = response.headers.get_content_charset() or "utf-8"
        try:
            return response.read().decode(charset, errors="replace")
        finally:
            response.close()

    def download(self, url: str, destination: Path) -> None:
        response = self._open(url)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as handle:
                while chunk := response.read(64 * 1024):
                    handle.write(chunk)
        finally:
            response.close()

    def _open(self, url: str):
        self._wait()
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            return self._opener.open(request, timeout=self.timeout)
        except (HTTPError, URLError, OSError) as error:
            if isinstance(error, HTTPError) and 300 <= error.code < 400:
                location = error.headers.get("Location", "未知地址")
                raise FetchError(f"页面重定向到登录或其他页面，未采集：{url} -> {location}") from error
            raise FetchError(f"无法访问 {url}：{error}") from error

    def _wait(self) -> None:
        remaining = self.delay - (time.monotonic() - self._last_request)
        if remaining > 0:
            time.sleep(remaining)
        self._last_request = time.monotonic()
