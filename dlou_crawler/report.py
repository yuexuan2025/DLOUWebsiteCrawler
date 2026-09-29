"""导出采集结果：articles.json + data.js + 网页报告台（index.html 为唯一入口）。"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from .crawler import Article

# 危险协议 / 混淆形态
_BAD_SCHEME = re.compile(
    r"^(?:javascript|data|vbscript|file|blob|about|livescript|mocha)\s*:",
    re.I,
)
_HTML_ENTITY = re.compile(r"&#x?[0-9a-f]+;?", re.I)


def _decode_url_noise(u: str) -> str:
    """去掉 HTML 实体、控制字符，便于协议判断。"""
    s = _HTML_ENTITY.sub("", u or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cc")
    return s.strip()


def _format_date(date: Optional[datetime]) -> str:
    if not date:
        return ""
    return date.strftime("%Y-%m-%d")


def _safe_url(url: str) -> str:
    """只允许 http/https 绝对地址；拒绝协议相对 //host、危险协议与混淆形态。"""
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    probe = _decode_url_noise(u)
    if not probe or _BAD_SCHEME.match(probe) or probe.startswith("//"):
        return ""
    if any(c in u for c in ("\n", "\r", "\t", "\x00", " ")):
        u = re.sub(r"[\s\x00]+", "", u)
        probe = _decode_url_noise(u)
        if not probe or _BAD_SCHEME.match(probe) or probe.startswith("//"):
            return ""
    parts = urlsplit(u)
    if parts.scheme and parts.scheme.lower() not in ("http", "https"):
        return ""
    if not parts.scheme:
        # 相对路径在 file:// 报告里无意义且易被利用，直接丢弃
        return ""
    if not parts.netloc:
        return ""
    return urlunsplit((parts.scheme.lower(), parts.netloc, parts.path, parts.query, ""))


def _escape_html(text: str) -> str:
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


_ALLOWED_TAGS = {
    "p", "br", "b", "strong", "i", "em", "u", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "ul", "ol", "img", "a", "blockquote", "pre", "code",
}
_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
}
_DROP_CONTENT_TAGS = {
    "script", "style", "iframe", "object", "embed", "link", "meta", "svg",
    "math", "form", "input", "button", "textarea", "select",
}
_VOID_OK = {"br", "img"}


class _SafeHTMLBuilder(HTMLParser):
    """白名单重建 HTML，防脚本/事件属性/危险协议（解析器级，优于正则替换）。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._drop_depth = 0
        self._open_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            self._drop_depth += 1
            return
        if self._drop_depth > 0:
            return
        if tag not in _ALLOWED_TAGS:
            return

        keep: list[str] = []
        for name, val in attrs:
            name = (name or "").lower()
            val = val or ""
            if name.startswith("on") or name in ("style", "srcset", "formaction", "xlink:href", "data"):
                continue
            if name not in _ALLOWED_ATTRS.get(tag, set()):
                continue
            if name in ("href", "src"):
                val = _safe_url(val)
                if not val:
                    continue
                # 只挡危险协议/相对路径；不按主机砍图，避免 CDN/图床图被误删
            keep.append(f'{name}="{_escape_html(val)}"')
        attr_str = (" " + " ".join(keep)) if keep else ""
        if tag == "a":
            attr_str += ' target="_blank" rel="noopener noreferrer"'
        if tag in _VOID_OK:
            self.parts.append(f"<{tag}{attr_str}>")
            return
        self.parts.append(f"<{tag}{attr_str}>")
        self._open_stack.append(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS or self._drop_depth > 0:
            if tag in _DROP_CONTENT_TAGS and self._drop_depth > 0:
                self._drop_depth = max(0, self._drop_depth - 1)
            return
        if tag not in _VOID_OK and tag in _ALLOWED_TAGS and self._open_stack and self._open_stack[-1] == tag:
            self._open_stack.pop()
            self.parts.append(f"</{tag}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if self._drop_depth > 0:
            return
        if tag not in _ALLOWED_TAGS:
            return
        if self._open_stack and self._open_stack[-1] == tag:
            self._open_stack.pop()
            self.parts.append(f"</{tag}>")
        elif tag in self._open_stack:
            # 容错：中间有未闭合标签时，补到匹配标签为止
            while self._open_stack and self._open_stack[-1] != tag:
                self.parts.append(f"</{self._open_stack.pop()}>")
            if self._open_stack:
                self._open_stack.pop()
                self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._drop_depth > 0:
            return
        if data:
            self.parts.append(_escape_html(data))

    def close(self) -> None:
        super().close()
        while self._open_stack:
            self.parts.append(f"</{self._open_stack.pop()}>")

    def result(self) -> str:
        return "".join(self.parts)


def sanitize_html(html: str) -> str:
    """白名单清洗，防脚本/事件属性/危险协议。"""
    if not html:
        return ""
    parser = _SafeHTMLBuilder()
    try:
        parser.feed(str(html))
        parser.close()
    except Exception:
        # 极端畸形输入：退回转义纯文本，绝不拼回原始 HTML
        return _escape_html(strip_tags_noop(str(html)))
    return parser.result()


def strip_tags_noop(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", str(html or ""))


def _article_to_dict(a: Article) -> dict:
    images = []
    for img in a.images or []:
        src = _safe_url(img.get("src", ""))
        if src:
            images.append({"src": src, "alt": img.get("alt", "") or ""})
    attachments = []
    for att in a.attachments or []:
        url = _safe_url(att.get("url", ""))
        if url:
            name = (att.get("name") or "").strip()
            # 附件名若是长 URL/路径，用文件名展示
            if (not name) or name.startswith(("http://", "https://", "/")) or len(name) > 80:
                name = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1] or "附件"
            attachments.append({"name": name, "url": url})
    return {
        "title": a.title or "",
        "url": _safe_url(a.url or ""),
        "category": a.category or "",
        "source": a.source or "",
        "date": _format_date(a.date),
        "content": sanitize_html(a.content or ""),
        "images": images,
        "attachments": attachments,
        "summary": getattr(a, "summary", "") or "",
    }


def _json_for_script(data) -> str:
    """嵌入 <script> 的 JSON，防止 </script> 与 U+2028/2029 逃逸。"""
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def _csv_cell(val: str) -> str:
    """防 Excel 公式注入。"""
    s = str(val or "")
    if s[:1] in ("=", "+", "-", "@", "\t", "\r"):
        s = "'" + s
    return s


def save_articles_json(articles: list[Article], output_path: str) -> str:
    """导出 articles.json（字段已清洗）。"""
    data = [_article_to_dict(a) for a in articles]
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return output_path


def save_articles_csv(articles: list[Article], output_path: str) -> str:
    """导出 CSV（Excel 可直接打开，UTF-8 BOM）。"""
    import csv

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    fields = ["date", "category", "source", "title", "url", "summary", "image_count", "attachment_count"]
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for a in articles:
            writer.writerow({
                "date": _csv_cell(_format_date(a.date)),
                "category": _csv_cell(a.category or ""),
                "source": _csv_cell(a.source or ""),
                "title": _csv_cell(a.title or ""),
                "url": _csv_cell(_safe_url(a.url or "")),
                "summary": _csv_cell(getattr(a, "summary", "") or ""),
                "image_count": len(a.images or []),
                "attachment_count": len(a.attachments or []),
            })
    return output_path


def export_web_report(articles: list[Article], output_dir: str, source_stats: Optional[list] = None) -> str:
    """
    生成唯一网页报告入口 output/index.html。
    同时写入 data.js（file:// 可直接加载），并复制 app.css / app.js。
    """
    from .crawler import SOURCES, CATEGORY_ORDER as CATS, GROUP_ICONS as ICONS

    os.makedirs(output_dir, exist_ok=True)

    # 移除历史双报告产物，只保留 index.html 一套
    for legacy in ("采集报告.html",):
        legacy_path = os.path.join(output_dir, legacy)
        if os.path.isfile(legacy_path):
            try:
                os.remove(legacy_path)
            except OSError:
                pass

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(articles),
        "categories": CATS,
        "category_icons": ICONS,
        "sources": [
            {"name": s["name"], "url": s["url"], "category": s["category"]}
            for s in SOURCES
        ],
        "articles": [_article_to_dict(a) for a in articles],
        "source_stats": source_stats or [],
    }
    data_js = os.path.join(output_dir, "data.js")
    with open(data_js, "w", encoding="utf-8") as f:
        f.write("window.__DLOU__ = " + _json_for_script(payload) + ";\n")

    # 复制网页三件套：优先 EXE 资源目录，再源码目录；不依赖当前工作目录
    src_roots = [
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # 仓库根
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),  # 上级
    ]
    if hasattr(__import__("sys"), "_MEIPASS"):
        src_roots.insert(0, __import__("sys")._MEIPASS)
    copied = 0
    used: dict[str, str] = {}
    for name in ("index.html", "app.css", "app.js"):
        for base in src_roots:
            src = os.path.join(base, name)
            if os.path.isfile(src):
                try:
                    with open(src, "rb") as f:
                        data = f.read()
                    with open(os.path.join(output_dir, name), "wb") as f:
                        f.write(data)
                    copied += 1
                    used[name] = src
                except OSError as e:
                    print(f"[warn] 复制 {name} 失败: {e}")
                break
    if copied < 3:
        print(f"[warn] 报告资源仅复制 {copied}/3，页面样式可能不完整：{used}")
    return os.path.join(output_dir, "index.html")
