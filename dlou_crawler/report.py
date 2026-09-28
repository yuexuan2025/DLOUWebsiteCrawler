"""导出采集结果：articles.json + data.js + 网页报告台（index.html 为唯一入口）。"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from .crawler import Article


def _format_date(date: Optional[datetime]) -> str:
    if not date:
        return ""
    return date.strftime("%Y-%m-%d")


def _safe_url(url: str) -> str:
    """只允许 http/https/相对站内路径。"""
    if not url or not isinstance(url, str):
        return ""
    u = url.strip()
    if u.lower().startswith(("javascript:", "data:", "vbscript:", "file:")):
        return ""
    parsed = urlparse(u)
    if parsed.scheme and parsed.scheme.lower() not in ("http", "https"):
        return ""
    return u


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


def sanitize_html(html: str) -> str:
    """白名单清洗，防脚本/事件属性/危险协议。"""
    if not html:
        return ""
    s = str(html)
    s = re.sub(r"(?is)<(script|style|iframe|object|embed|link|meta)\b[^>]*>.*?</\1>", "", s)
    s = re.sub(r"(?is)<(script|style|iframe|object|embed|link|meta)\b[^>]*/?>", "", s)

    def _clean_tag(m: re.Match) -> str:
        tag = (m.group(1) or "").lower()
        if tag not in _ALLOWED_TAGS:
            return ""
        attrs_raw = m.group(2) or ""
        keep: list[str] = []
        for am in re.finditer(
            r'''([a-zA-Z_:][-\w:.]*)\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'>]+))''',
            attrs_raw,
        ):
            name = am.group(1).lower()
            val = am.group(3) or am.group(4) or am.group(5) or ""
            if name.startswith("on"):
                continue
            if name not in _ALLOWED_ATTRS.get(tag, set()):
                continue
            if name in ("href", "src"):
                val = _safe_url(val)
                if not val:
                    continue
            keep.append(f'{name}="{_escape_html(val)}"')
        attr_str = (" " + " ".join(keep)) if keep else ""
        if tag == "a" and not any(k.startswith("rel=") for k in keep):
            attr_str += ' rel="noopener noreferrer"'
        return f"<{tag}{attr_str}>"

    s = re.sub(r"<([a-zA-Z0-9]+)((?:\s+[^<>]*?)?)(/?)>", _clean_tag, s)
    s = re.sub(
        r"</([a-zA-Z0-9]+)>",
        lambda m: f"</{m.group(1)}>" if m.group(1).lower() in _ALLOWED_TAGS else "",
        s,
    )
    return s


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
            attachments.append({"name": att.get("name", "") or "", "url": url})
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
    """嵌入 <script> 的 JSON，防止 </script> 逃逸。"""
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


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
                "date": _format_date(a.date),
                "category": a.category or "",
                "source": a.source or "",
                "title": a.title or "",
                "url": _safe_url(a.url or ""),
                "summary": getattr(a, "summary", "") or "",
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

    # 复制网页三件套（源码目录 source/ 或 EXE 资源目录）
    src_roots = [
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # source/
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),  # 项目根
        os.getcwd(),
    ]
    if hasattr(__import__("sys"), "_MEIPASS"):
        src_roots.insert(0, __import__("sys")._MEIPASS)
    for name in ("index.html", "app.css", "app.js"):
        for base in src_roots:
            src = os.path.join(base, name)
            if os.path.isfile(src):
                try:
                    with open(src, "rb") as f:
                        data = f.read()
                    with open(os.path.join(output_dir, name), "wb") as f:
                        f.write(data)
                except OSError:
                    pass
                break

    return os.path.join(output_dir, "index.html")
