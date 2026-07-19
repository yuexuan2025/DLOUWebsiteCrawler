from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from .client import FetchError, PoliteClient
from .html_tools import Link, date_from_text, date_from_url, is_article_link, is_attachment, parse_page
from .models import Article, Attachment


ALLOWED_HOSTS = frozenset({"www.dlou.edu.cn", "news.dlou.edu.cn"})
SOURCES = (
    ("学校主页新闻", "https://www.dlou.edu.cn/"),
    ("信息公告", "https://www.dlou.edu.cn/89/list.htm"),
    ("新闻网", "https://news.dlou.edu.cn/"),
)


class DlouCrawler:
    def __init__(
        self,
        client: PoliteClient,
        pages_per_source: int,
        max_articles: int,
        download_files: bool,
        output_dir: Path,
    ) -> None:
        self.client = client
        self.pages_per_source = pages_per_source
        self.max_articles = max_articles
        self.download_files = download_files
        self.output_dir = output_dir
        self.warnings: list[str] = []

    @staticmethod
    def is_allowed(url: str) -> bool:
        parts = urlsplit(url)
        return parts.scheme in {"http", "https"} and parts.hostname in ALLOWED_HOSTS

    @staticmethod
    def _canonical_url(url: str) -> str:
        """The homepage contains some HTTP links; use HTTPS for every request."""
        parts = urlsplit(url)
        return urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))

    def crawl(self) -> list[Article]:
        candidates: dict[str, tuple[str, str]] = {}
        for category, source_url in SOURCES:
            self._collect_listing_links(category, source_url, candidates)
        articles: list[Article] = []
        seen_titles: set[str] = set()
        for url, (title, category) in candidates.items():
            article = self._collect_article(url, title, category)
            title_key = article.title.casefold() if article else ""
            if article and title_key not in seen_titles:
                articles.append(article)
                seen_titles.add(title_key)
            if len(articles) >= self.max_articles:
                break
        return articles

    def _collect_listing_links(
        self, category: str, source_url: str, candidates: dict[str, tuple[str, str]]
    ) -> None:
        pages = deque([source_url])
        seen: set[str] = set()
        while pages and len(seen) < self.pages_per_source:
            url = pages.popleft()
            if url in seen or not self._permitted(url):
                continue
            seen.add(url)
            try:
                page = parse_page(self.client.get_text(url), url)
            except FetchError as error:
                self.warnings.append(str(error))
                continue
            for link in page.links:
                if self.is_allowed(link.url) and is_article_link(link):
                    article_url = self._canonical_url(link.url)
                    candidates.setdefault(article_url, (link.text, self._category_for(article_url, category)))
                if self._is_next_page(link, url) and self.is_allowed(link.url):
                    pages.append(self._canonical_url(link.url))

    def _collect_article(self, url: str, fallback_title: str, category: str) -> Article | None:
        if not self._permitted(url):
            return None
        try:
            page = parse_page(self.client.get_text(url), url)
        except FetchError as error:
            self.warnings.append(str(error))
            return Article(
                title=fallback_title,
                url=url,
                category=category,
                published_at=None,
                content="正文需要登录或暂时无法公开访问，未采集。请通过原文链接在学校网站查看。",
            )
        title = page.headings[0] if page.headings else page.title or fallback_title
        attachments = [
            Attachment(link.text, link.url)
            for link in page.links
            if self.is_allowed(link.url) and is_attachment(link.url)
        ]
        article = Article(
            title=title,
            url=url,
            category=category,
            published_at=date_from_text(page.text) or date_from_url(url),
            content=page.text,
            attachments=attachments,
        )
        if self.download_files:
            self._download_attachments(article)
        return article

    def _download_attachments(self, article: Article) -> None:
        for index, attachment in enumerate(article.attachments, start=1):
            if not self._permitted(attachment.url):
                continue
            filename = self._safe_filename(attachment.url, index)
            destination = self.output_dir / "files" / filename
            try:
                self.client.download(attachment.url, destination)
                attachment.local_path = str(destination)
            except FetchError as error:
                self.warnings.append(str(error))

    def _permitted(self, url: str) -> bool:
        if not self.is_allowed(url):
            self.warnings.append(f"已跳过非官网链接：{url}")
            return False
        if not self.client.can_fetch(url):
            self.warnings.append(f"robots.txt 不允许采集：{url}")
            return False
        return True

    @staticmethod
    def _is_next_page(link: Link, current_url: str) -> bool:
        return "下一页" in link.text and link.url != current_url

    @staticmethod
    def _safe_filename(url: str, index: int) -> str:
        original = Path(unquote(urlsplit(url).path)).name or f"attachment-{index}"
        cleaned = re.sub(r'[<>:"/\\|?*]', "_", original)
        return f"{index:03d}-{cleaned}"

    @staticmethod
    def _category_for(url: str, fallback: str) -> str:
        if "/c89a" in url:
            return "信息公告"
        if "/c1281a" in url:
            return "综合新闻"
        if "/c4820a" in url:
            return "学校要闻"
        return fallback
