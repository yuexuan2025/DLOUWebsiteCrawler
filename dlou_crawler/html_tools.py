"""HTML 解析工具：列表链接、正文、日期、附件 — 兼容站群多种模板。"""
from __future__ import annotations

import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


# ─────────────────────────────────────────────
# 正文抽取
# ─────────────────────────────────────────────
CONTENT_INDICATORS = [
    "article", "content", "main", "text", "detail",
    "news_content", "v_news_content", "article-content",
    "entry-content", "post-content", "wp-content",
    "newsdetail", "news-detail", "news_detail",
    "artdetail", "art-detail", "art_detail",
    "list-content", "show-content", "view-content",
    "content-main", "main-content",
    "article-body", "news-body", "text-content",
    "trs_editor", "custom_unionstyle", "wp_articlecontent",
    "vsb_content", "content_area", "nr_con", "xl_con",
    "zoom", "wzcon", "nr", "zz", "jianjie", "detail_con",
    "article_con", "news_con", "txt", "body_con",
]

SKIP_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "form", "iframe"}

# 不应进入正文的图片
_IMG_NOISE = (
    "visitcount", "counter", "logo", "banner", "footer", "header",
    "icon_rar", "icon_pdf", "icon_doc", "icon_xls", "icon_ppt",
    "icon_zip", "icon_fj", "pre.jpg", "next.jpg",
    "/tpl/", "/template", "/_js/", "/_css/",
    "loading.gif", "nopic", "nopicture", "blank.gif",
)


def _is_noise_image(src: str) -> bool:
    s = (src or "").lower()
    if not s or s.startswith("data:"):
        return True
    return any(x in s for x in _IMG_NOISE)


class _ArticleExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.content_parts: list[str] = []
        self.images: list[dict] = []
        self.attachments: list[dict] = []
        self.meta_desc = ""
        self.meta_date = ""

        self._in_title = False
        self._in_content = False
        self._content_depth = 0
        self._skip_depth = 0
        self._in_meta = False
        self._current_href: str | None = None
        self._current_link_text: list[str] = []
        self._text_fallback: list[str] = []
        self._seen_imgs: set[str] = set()
        self._seen_atts: set[str] = set()

    # -- helpers --
    def _enter_skip(self):
        self._skip_depth += 1

    def _leave_skip(self):
        self._skip_depth = max(0, self._skip_depth - 1)

    def _match_content(self, class_attr: str, id_attr: str) -> bool:
        blob = f"{class_attr} {id_attr}".lower()
        return any(ind in blob for ind in CONTENT_INDICATORS)

    # -- parser hooks --
    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag in SKIP_TAGS:
            self._enter_skip()
            return
        if self._skip_depth > 0:
            return

        if tag == "title":
            self._in_title = True
            return

        if tag == "meta":
            name = (attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            content = attrs_dict.get("content") or ""
            if name in ("description", "og:description") and content and not self.meta_desc:
                self.meta_desc = content
            if name in ("pubdate", "publishdate", "og:published_time", "article:published_time"):
                if content and not self.meta_date:
                    self.meta_date = content
            return

        if tag == "img":
            src = attrs_dict.get("src") or attrs_dict.get("data-src") or attrs_dict.get("data-original") or ""
            alt = attrs_dict.get("alt") or ""
            if src and src not in self._seen_imgs and not _is_noise_image(src):
                self._seen_imgs.add(src)
                self.images.append({"src": src, "alt": alt})
                if self._in_content:
                    self.content_parts.append(f'<img src="{src}" alt="{alt}">')
            return

        if tag == "a":
            href = attrs_dict.get("href") or ""
            self._current_href = href
            self._current_link_text = []
            return

        class_attr = attrs_dict.get("class") or ""
        id_attr = attrs_dict.get("id") or ""

        if not self._in_content:
            if self._match_content(class_attr, id_attr):
                self._in_content = True
                self._content_depth = 1
        else:
            self._content_depth += 1

        if self._in_content:
            if tag == "p":
                self.content_parts.append("<p>")
            elif tag == "br":
                self.content_parts.append("<br>")
            elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.content_parts.append(f"<{tag}>")
            elif tag == "li":
                self.content_parts.append("<p>· ")
            elif tag in ("strong", "b"):
                self.content_parts.append("<b>")
            elif tag in ("em", "i"):
                self.content_parts.append("<i>")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._leave_skip()
            return
        if self._skip_depth > 0:
            return

        if tag == "title":
            self._in_title = False
            return

        if tag == "a" and self._current_href:
            link_text = "".join(self._current_link_text).strip()
            href = self._current_href
            if is_attachment(href, link_text):
                key = href.lower()
                if key not in self._seen_atts:
                    self._seen_atts.add(key)
                    self.attachments.append({"name": link_text or href, "url": href})
            if self._in_content and link_text:
                self.content_parts.append(f'<a href="{href}">{link_text}</a>')
            self._current_href = None
            self._current_link_text = []
            return

        if self._in_content:
            self._content_depth -= 1
            if self._content_depth <= 0:
                self._in_content = False
                self._content_depth = 0

            if tag == "p":
                self.content_parts.append("</p>")
            elif tag == "li":
                self.content_parts.append("</p>")
            elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.content_parts.append(f"</{tag}>")
            elif tag in ("strong", "b"):
                self.content_parts.append("</b>")
            elif tag in ("em", "i"):
                self.content_parts.append("</i>")

    def handle_data(self, data):
        if self._skip_depth > 0:
            return

        if self._in_title:
            self.title += data
            return

        if self._current_href is not None:
            self._current_link_text.append(data)
            # 同时收集纯文本，作为无标记正文的兜底
            if data.strip():
                self._text_fallback.append(data)
            return

        if self._in_content and data.strip():
            self.content_parts.append(data)
        elif data.strip() and len(self._text_fallback) < 400:
            self._text_fallback.append(data)


def extract_article(html: str, base_url: str = "") -> dict:
    """从详情页 HTML 抽取 title/content/images/attachments/summary。"""
    empty = {"title": "", "content": "", "images": [], "attachments": [], "summary": "", "date": None}
    if not html:
        return empty

    parser = _ArticleExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass

    title = (parser.title or "").strip()
    # title 可能带站名后缀
    if "|" in title:
        parts = [p.strip() for p in title.split("|") if p.strip()]
        if parts:
            title = parts[0] if len(parts[0]) >= 4 else (parts[-1] if parts else title)
    if "—" in title and len(title) > 40:
        title = title.split("—")[0].strip()
    title = clean_title(title)

    content = "".join(parser.content_parts)
    content = re.sub(r"[ \t\r\f\v]+", " ", content)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    # 去掉明显是导航菜单的段落（大量 list.htm 链接 + 短标题）
    content = _strip_nav_like(content)

    # 若仍残留大量导航链接，只保留最长的实质文本块
    if content.count("list.htm") + content.count("list.psp") + content.count('href="/') >= 6:
        content = _keep_main_block(content)

    # 清理空段落
    content = re.sub(r"(?:</p>\s*){2,}", "</p>", content)
    content = re.sub(r"^\s*(?:</p>\s*)+", "", content)
    content = re.sub(r"\n{3,}", "\n\n", content).strip()

    # 发布元数据 / 版权页脚噪声
    content = _strip_meta_noise(content)
    # 导航前缀剪裁（从真正标题起读）
    content = _trim_leading_nav(content)

    # 无标记正文时用文本兜底
    if len(strip_html(content)) < 40 and parser._text_fallback:
        fallback = " ".join(t.strip() for t in parser._text_fallback if t.strip())
        fallback = re.sub(r"\s+", " ", fallback).strip()
        # 菜单噪声兜底也过滤
        if not _looks_like_nav(fallback) and len(fallback) > 40:
            content = f"<p>{fallback}</p>"
            content = _strip_meta_noise(content)

    images = []
    for img in parser.images:
        src = img["src"]
        if _is_noise_image(src):
            continue
        if base_url and src:
            src = urljoin(base_url, src)
        images.append({"src": src, "alt": img.get("alt", "")})

    attachments = []
    for att in parser.attachments:
        url = att["url"]
        if base_url and url:
            url = urljoin(base_url, url)
        attachments.append({"name": att["name"], "url": url})

    # 标题为空时尝试从正文 / meta
    if not title:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", content, re.I | re.S)
        if m:
            title = strip_html(m.group(1)).strip()

    summary = make_summary(content) or (parser.meta_desc or "")[:120]

    # 日期：meta → 正文 → 标题
    article_date = None
    if parser.meta_date:
        article_date = date_from_text(parser.meta_date)
    if not article_date:
        article_date = date_from_text(content) or date_from_text(title) or date_from_text(parser.meta_desc or "")

    return {
        "title": title,
        "content": content,
        "images": images,
        "attachments": attachments,
        "summary": summary,
        "date": article_date,
    }


def strip_html(html: str) -> str:
    """去掉 HTML 标签，返回纯文本。"""
    return re.sub(r"<[^>]+>", " ", html or "")


def _looks_like_nav(text: str) -> bool:
    """整段像导航/页脚：含大量 list.htm / 极短链接词。"""
    if not text:
        return False
    list_refs = len(re.findall(r"list\.(?:htm|psp|html)", text, re.I))
    if list_refs >= 4:
        return True
    # 短词占比过高
    words = [w for w in re.split(r"[\s、，。|·/<>]+", strip_html(text)) if w]
    if len(words) >= 6:
        short = sum(1 for w in words if len(w) <= 6)
        if short / len(words) > 0.8:
            return True
    return False


def _is_nav_para(para: str) -> bool:
    """单个段落是否为导航项：指向 list/首页 + 文本很短，或是「· 菜单词」。"""
    text = strip_html(para).strip()
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', para, flags=re.I)

    # 「· 菜单词」形态（学院站侧栏）
    if re.match(r"^[·•\-–—]\s*\S{1,8}$", text):
        return True

    if any(re.search(r"list\.(htm|psp|html)$", h.split("?")[0].lower()) or h.rstrip("/").endswith(("main.htm", "main.psp")) for h in hrefs):
        if len(text) <= 16:
            return True

    if "list.htm" not in para.lower() and "list.psp" not in para.lower():
        # 纯短导航文本 + 多链接
        if hrefs and len(text) <= 10:
            return True
        return False

    if len(text) <= 16:
        return True
    nav_words = (
        "学院概况", "学院简介", "现任领导", "组织机构", "党群工作", "师资队伍",
        "人才培养", "本科生培养", "研究生培养", "学科科研", "学科建设", "科研成果",
        "团学工作", "团学活动", "招生就业", "下载专区", "教学工作", "学校首页",
        "本站首页", "理论学习", "组织生活", "师德师风", "廉政建设", "校友风采",
        "专业简介", "创新创业", "质量体系", "教学成果", "研究生活动", "学术交流",
        "电气与信息", "机械工程系", "土木工程系", "基础部", "图书馆", "招生就业",
    )
    if any(w in text for w in nav_words) and len(text) < 20:
        return True
    return False


def _strip_nav_like(content: str) -> str:
    """删除像导航菜单的段落（含 list 链接 + 短文本）。"""
    def clean_para(m):
        para = m.group(0)
        if _is_nav_para(para) or _looks_like_nav(para):
            return ""
        return para

    content = re.sub(r"<p\b[^>]*>.*?</p>", clean_para, content, flags=re.I | re.S)
    content = re.sub(r"<li\b[^>]*>.*?</li>", clean_para, content, flags=re.I | re.S)
    # 清掉空壳标签
    content = re.sub(r"<(p|i|b|br)\b[^>]*>\s*</\1>", "", content, flags=re.I)
    content = re.sub(r"(<br\s*/?>\s*){3,}", "<br>", content, flags=re.I)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def _keep_main_block(content: str) -> str:
    """按段落切开，保留「非导航且最长」的连续块。"""
    parts = re.split(r"(?<=</p>)\s*", content)
    blocks: list[str] = []
    current: list[str] = []

    def flush():
        if current:
            blocks.append("".join(current))
            current.clear()

    for part in parts:
        if not part.strip():
            continue
        if _is_nav_para(part) or _looks_like_nav(part):
            flush()
        else:
            current.append(part)
    flush()

    if not blocks:
        return content

    # 取文本最长的块
    def score(b: str) -> int:
        return len(strip_html(b))

    best = max(blocks, key=score)
    return best.strip() if score(best) >= 30 else content


def _trim_leading_nav(content: str) -> str:
    """若正文前缀是导航，从第一个实质 <h1>/<h2> 起保留。"""
    if not content:
        return content
    # 找到像文章标题的 h1/h2（长度>=8 的可见文本）
    for m in re.finditer(r"<h([12])[^>]*>(.*?)</h\1>", content, flags=re.I | re.S):
        text = strip_html(m.group(2)).strip()
        if len(text) >= 8:
            tail = content[m.start() :]
            # 前缀若像导航则剪掉
            head = content[: m.start()]
            head_text = strip_html(head)
            if _looks_like_nav(head) or head_text.count("·") >= 3 or len(head_text) < 20:
                return tail.strip()
            # 前缀过长且含大量短链，也剪
            if len(head) > 200 and head.lower().count("list.") >= 2:
                return tail.strip()
            break
    return content


def _strip_meta_noise(html: str) -> str:
    """去掉发布元数据行、版权页脚等展示噪声。"""
    s = html or ""
    # 整段去掉：发布者/时间/浏览量/撰稿/审核/版权
    s = re.sub(
        r"<p[^>]*>\s*(?:发布者|发布时间|发布人|发布日期|浏览次数|点击量|责任编辑|审核发布|撰稿人|来源)[:：][^<]*</p>",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(
        r"(?:发布者|发布时间|发布人|发布日期|浏览次数|点击量|责任编辑|审核发布|撰稿人)[:：]\s*[\d\-/\s:年月日]*\s*(?:浏览次数[:：]?\d+)?",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(
        r"(?:版权所有|Copyright|All rights reserved|辽ICP备\d+号)[^<\n]*",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(
        r"<p[^>]*>\s*(?:地址：|电话：|邮箱：|E-mail：|邮编：|校办电话)[^<]*</p>",
        "",
        s,
        flags=re.I,
    )
    # 残留中文日期戳行「发布时间：2026-09-28   浏览次数:28」
    s = re.sub(r"发布时间[:：][\d\-/\s]+浏览次数[:：]?\d+", "", s, flags=re.I)
    return s.strip()


def make_summary(content: str, limit: int = 120) -> str:
    """从正文生成展示用摘要。"""
    text = strip_html(content)
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


# ─────────────────────────────────────────────
# 日期解析
# ─────────────────────────────────────────────
def date_from_text(text) -> datetime | None:
    """从文本中解析日期。"""
    if not isinstance(text, str) or not text.strip():
        return None

    patterns = [
        r"(\d{4})\s*[-/年.]\s*(\d{1,2})\s*[-/月.]\s*(\d{1,2})",
        r"(?<!\d)(\d{4})(\d{2})(\d{2})(?!\d)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                    return datetime(y, m, d)
            except (ValueError, IndexError):
                continue
    return None


def date_from_url(url) -> datetime | None:
    """从 URL 路径解析日期。"""
    if not isinstance(url, str) or not url.strip():
        return None

    path = urlparse(url).path
    patterns = [
        r"/(\d{4})/(\d{2})(\d{2})/",
        r"/(\d{4})[-_](\d{2})[-_](\d{2})/",
        r"/(\d{4})/(\d{1,2})/(\d{1,2})/",
    ]
    for pattern in patterns:
        match = re.search(pattern, path)
        if match:
            try:
                y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if 2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                    return datetime(y, m, d)
            except (ValueError, IndexError):
                continue
    return None


# ─────────────────────────────────────────────
# 链接识别
# ─────────────────────────────────────────────
NOISE_TITLES = {
    "联系我们", "院系纵览", "网站首页", "学校概况", "返回首页", "返回顶部",
    "更多", "更多>>", "更多+", "查看更多", "next", "previous", "more",
    "首页", "上一页", "下一页", "尾页", "第一页", "下载", "附件",
    "设为首页", "加入收藏", "网站地图", "版权声明", "友情链接",
    "学校首页", "本站首页", "english", "en", "首页 >",
    # 运行时遇到的废文标题
    "提示信息", "联系方式", "联系我们", "公众号", "二维码",
    "新闻快递", "常用下载", "通知公告", "新闻动态",
    "通知公告 - 大连海洋大学", "新闻快递 - 大连海洋大学", "常用下载 - 大连海洋大学",
    "本科生招生", "研究生招生", "招生动态", "公告通知",
    "视频专区", "招生政策", "招生计划", "历年分数", "宣讲行程",
    "智能咨询", "录取查询", "走进海大", "快速通道", "相关链接",
    "院系介绍", "专业介绍", "走进大海大",
}

# 标题清洗：去掉前缀日期、站名后缀
_TITLE_PREFIX_DATE = re.compile(r"^\s*[\[（(]?\s*\d{1,2}[-/月]\s*\d{1,2}(?:日)?\s*[\]）)]?\s*")
_TITLE_SITE_SUFFIX = re.compile(r"\s*[-|—|_|·]\s*(?:大连海洋大学|DLOU|新闻网|共青团在线|大连海洋大学官网)\s*$", re.I)


def clean_title(title: str) -> str:
    """规范化标题：去日期前缀、站名后缀、异常空白。"""
    if not title:
        return ""
    t = re.sub(r"\s+", " ", str(title)).strip()
    t = _TITLE_PREFIX_DATE.sub("", t).strip()
    t = _TITLE_SITE_SUFFIX.sub("", t).strip()
    return t


def is_noise_title(title: str) -> bool:
    """是否为废文/栏目壳标题。"""
    t = (title or "").strip()
    if not t:
        return True
    if t.lower() in NOISE_TITLES or t in NOISE_TITLES:
        return True
    # 纯栏目名 / 极短
    if len(t) < 4:
        return True
    if re.fullmatch(r"[\s\-–—|·.。、,，]*", t):
        return True
    return False

SKIP_EXT = (
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".mp3", ".mp4", ".avi", ".mov", ".wma",
    ".css", ".js", ".json", ".xml", ".rss", ".apk", ".exe",
)

ATTACH_EXT = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".7z", ".txt", ".csv", ".wps", ".et",
)

DOWNLOAD_WORDS = ("下载", "附件", "附表", "附录", "相关下载", "点击下载", "表格下载")


def is_article_link(href, text=None) -> bool:
    """判断是否文章正文链接。"""
    if not isinstance(href, str) or not href.strip():
        return False

    href_lower = href.lower().strip()
    if href_lower.startswith(("javascript:", "#", "mailto:", "tel:", "data:")):
        return False

    parsed = urlparse(href)
    path = parsed.path.lower()

    if not path or path == "/":
        return False

    # 站群首页 / 栏目列表
    if path.endswith(("/main.htm", "/main.psp", "/index.htm", "/index.html", "/index.psp")):
        return False
    if re.search(r"/(list|list\d+)\.(htm|html|psp|jspx)$", path):
        return False

    # 附件不是文章
    if any(path.endswith(ext) for ext in SKIP_EXT):
        # 但 page.htm 后带 hash 的仍是文章
        if "page.htm" not in path and "/f/newscenter/article/" not in path:
            return False

    # 站群正文页
    if re.search(r"/\d{4}/\d{3,4}/[a-z]\d+a\d+", path):
        return True
    if "page.htm" in path or path.endswith("/page.psp"):
        return True

    # 招生网等独立 CMS
    if re.search(r"/f/newscenter/article/[0-9a-f]{16,}", path):
        return True

    # 常见正文路径
    if re.search(r"/(info|article|news|content|detail|show|view)/\d+", path):
        return True

    # 有文章语义的路径关键词
    indicators = (
        "/article", "/news", "/notice", "/announce",
        "/info", "/detail", "/content", "/show/", "/view/",
        "/read/", "/art/", "/wen/", "/xxgk/",
    )
    if not any(ind in path for ind in indicators):
        return False

    # 标题过滤
    if text is not None and isinstance(text, str):
        t = text.strip()
        if len(t) < 4:
            return False
        if t.lower() in NOISE_TITLES or t in NOISE_TITLES:
            return False

    return True


def is_attachment(href, text=None) -> bool:
    """仅识别真实文件附件，排除「下载中心」等栏目入口。"""
    if not isinstance(href, str) or not href.strip():
        return False

    href_lower = href.lower().split("?")[0].split("#")[0]

    # 栏目页 / 列表页不是附件
    if re.search(r"/(list|list\d+)\.(htm|psp|html)$", href_lower):
        return False
    if href_lower.endswith((".htm", ".html", ".psp", ".jspx")):
        return False

    # 真实文件扩展名
    if any(href_lower.endswith(ext) for ext in ATTACH_EXT):
        return True

    # 仅当 URL 指向文件、且文案像下载时才算附件（避免「下载专区」栏目链）
    if text and isinstance(text, str):
        t = text.strip()
        if len(t) >= 4 and any(w in t for w in DOWNLOAD_WORDS):
            if re.search(r"\.(pdf|docx?|xlsx?|pptx?|zip|rar|7z|txt|csv)($|\?)", href_lower):
                return True
    return False


# ─────────────────────────────────────────────
# 列表链接抽取
# ─────────────────────────────────────────────
def extract_list_links(html: str, base_url: str) -> list[dict]:
    """从列表页抽取文章链接。"""
    if not html:
        return []

    class _ListLinkExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self._current_href: str | None = None
            self._current_text: list[str] = []
            self._skip_depth = 0
            self.found_links: list[dict] = []
            self._seen_urls: set[str] = set()

        def handle_starttag(self, tag, attrs):
            if tag in SKIP_TAGS:
                self._skip_depth += 1
                return
            if self._skip_depth > 0:
                return

            if tag == "a":
                attrs_dict = dict(attrs)
                href = attrs_dict.get("href") or ""
                if href:
                    self._current_href = href
                    self._current_text = []

        def handle_endtag(self, tag):
            if tag in SKIP_TAGS:
                self._skip_depth = max(0, self._skip_depth - 1)
                return
            if self._skip_depth > 0:
                return

            if tag == "a" and self._current_href is not None:
                text = "".join(self._current_text).strip()
                text = re.sub(r"\s+", " ", text)
                if is_article_link(self._current_href, text):
                    url = urljoin(base_url, self._current_href)
                    # 去掉锚点
                    url = url.split("#")[0]
                    if url and url not in self._seen_urls:
                        self._seen_urls.add(url)
                        self.found_links.append({
                            "url": url,
                            "title": text,
                            "date": date_from_url(url) or date_from_text(text),
                        })
                    elif text:
                        for link in self.found_links:
                            if link["url"] == url and not link["title"]:
                                link["title"] = text
                                break
                self._current_href = None
                self._current_text = []

        def handle_data(self, data):
            if self._skip_depth > 0:
                return
            if self._current_href is not None:
                self._current_text.append(data)

    parser = _ListLinkExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass

    for link in parser.found_links:
        if not link.get("date"):
            link["date"] = date_from_url(link.get("url", ""))

    return parser.found_links
