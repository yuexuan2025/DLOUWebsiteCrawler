"""大连海洋大学官网采集器 — 核心数据模型与采集流程。

分类与栏目对齐官网结构：
  学校要闻 / 通知公告 / 学术科研 / 人才培养 / 教学单位 / 职能部门
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from .client import HttpClient
from .html_tools import (
    extract_list_links, extract_article, date_from_text, date_from_url,
    clean_title, is_noise_title, strip_html,
)


@dataclass
class Article:
    title: str = ""
    url: str = ""
    category: str = ""
    source: str = ""
    date: Optional[datetime] = None
    content: str = ""
    images: list = field(default_factory=list)
    attachments: list = field(default_factory=list)
    summary: str = ""


# ─────────────────────────────────────────────────────────────
# 采集源：严格对齐官网导航与首页栏目
# ─────────────────────────────────────────────────────────────
SOURCES: list[dict] = [
    # ═══ 学校要闻（新闻网 · 宣传部） ═══
    {"name": "学校要闻", "url": "http://news.dlou.edu.cn/1281/list.htm", "category": "学校要闻", "group": "学校要闻"},
    {"name": "综合新闻", "url": "http://news.dlou.edu.cn/jcfc/list.htm", "category": "学校要闻", "group": "学校要闻"},
    {"name": "校园快讯", "url": "http://news.dlou.edu.cn/1288/list.htm", "category": "学校要闻", "group": "学校要闻"},
    {"name": "媒体报道", "url": "http://news.dlou.edu.cn/1283/list.htm", "category": "学校要闻", "group": "学校要闻"},
    {"name": "校园喜报", "url": "http://news.dlou.edu.cn/xyxb/list.htm", "category": "学校要闻", "group": "学校要闻"},
    {"name": "图片新闻", "url": "http://news.dlou.edu.cn/gdtp/list.htm", "category": "学校要闻", "group": "学校要闻"},

    # ═══ 通知公告（主站 · 首页 NOTICE） ═══
    {"name": "信息公告", "url": "https://www.dlou.edu.cn/89/list.htm", "category": "通知公告", "group": "通知公告"},
    {"name": "学校公文", "url": "https://www.dlou.edu.cn/91/list.htm", "category": "通知公告", "group": "通知公告"},
    {"name": "下载专区", "url": "http://news.dlou.edu.cn/1290/list.htm", "category": "通知公告", "group": "通知公告"},
    {"name": "下载表格", "url": "http://news.dlou.edu.cn/xzzq/list.htm", "category": "通知公告", "group": "通知公告"},
    {"name": "宣传通知", "url": "http://news.dlou.edu.cn/tztg/list.htm", "category": "通知公告", "group": "通知公告"},

    # ═══ 学术科研（首页 ACADEMIC + 科技处） ═══
    {"name": "学术海大", "url": "https://www.dlou.edu.cn/190/list.htm", "category": "学术科研", "group": "学术科研"},
    {"name": "科技处·通知公告", "url": "http://kjc.dlou.edu.cn/tzgg/list.htm", "category": "学术科研", "group": "学术科研"},
    {"name": "科技处·科技要闻", "url": "http://kjc.dlou.edu.cn/kjyw/list.htm", "category": "学术科研", "group": "学术科研"},
    {"name": "科技处·成果发布", "url": "http://kjc.dlou.edu.cn/cgfb/list.htm", "category": "学术科研", "group": "学术科研"},
    {"name": "科技处·校园快讯", "url": "http://kjc.dlou.edu.cn/xykx/list.htm", "category": "学术科研", "group": "学术科研"},

    # ═══ 人才培养（教务处 / 研究生院 / 招生就业处 / 招生办） ═══
    {"name": "教务处·通知公告", "url": "http://jwch.dlou.edu.cn/8998/list.htm", "category": "人才培养", "group": "人才培养"},
    {"name": "教务处·新闻动态", "url": "http://jwch.dlou.edu.cn/8999/list.htm", "category": "人才培养", "group": "人才培养"},
    {"name": "研究生院·通知公告", "url": "http://master.dlou.edu.cn/tzgg/list.htm", "category": "人才培养", "group": "人才培养"},
    {"name": "研究生院·新闻动态", "url": "http://master.dlou.edu.cn/xwdt/list.htm", "category": "人才培养", "group": "人才培养"},
    {"name": "研究生院·招生工作", "url": "http://master.dlou.edu.cn/9037/list.htm", "category": "人才培养", "group": "人才培养"},
    {"name": "研究生院·培养工作", "url": "http://master.dlou.edu.cn/9038/list.htm", "category": "人才培养", "group": "人才培养"},
    {"name": "研究生院·就业工作", "url": "https://master.dlou.edu.cn/9068/list.htm", "category": "人才培养", "group": "人才培养"},
    {"name": "招生就业处·新闻动态", "url": "https://zsjy.dlou.edu.cn/9776/list.htm", "category": "人才培养", "group": "人才培养"},
    {"name": "招生就业处·通知公告", "url": "https://zsjy.dlou.edu.cn/9777/list.htm", "category": "人才培养", "group": "人才培养"},
    {"name": "本科招生·招生动态", "url": "http://bkzsw.dlou.edu.cn/f/newsCenter/articles/3210fc07f304485283695d6ae47c0aeb", "category": "人才培养", "group": "人才培养"},
    {"name": "本科招生·公告通知", "url": "http://bkzsw.dlou.edu.cn/f/newsCenter/articles/ff5128fc1f074f92940c35b18fe072dc", "category": "人才培养", "group": "人才培养"},
    {"name": "就业信息网", "url": "https://dlou.jysd.com/", "category": "人才培养", "group": "人才培养"},
    {"name": "继续教育", "url": "http://jxjyxy.dlou.edu.cn/", "category": "人才培养", "group": "人才培养"},

    # ═══ 教学单位（各学院 · 官网「教学单位」导航） ═══
    {"name": "水产与生命学院", "url": "https://life.dlou.edu.cn/907/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "水产与生命学院·公告", "url": "https://life.dlou.edu.cn/908/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "海洋科技与环境学院", "url": "https://hhxy.dlou.edu.cn/xyxw_8738/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "海洋科技与环境学院·公告", "url": "https://hhxy.dlou.edu.cn/tzgg/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "食品科学与工程学院", "url": "https://food.dlou.edu.cn/1680/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "海洋与土木工程学院", "url": "https://tmgc.dlou.edu.cn/3822/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "机械与动力工程学院", "url": "https://jixie.dlou.edu.cn/4323/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "航海与船舶工程学院", "url": "https://sea.dlou.edu.cn/1533/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "信息工程学院", "url": "https://xxgc.dlou.edu.cn/3965/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "信息工程学院·公告", "url": "https://xxgc.dlou.edu.cn/3961/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "经济管理学院", "url": "https://jjgl.dlou.edu.cn/2128/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "海洋法律与人文学院", "url": "https://fxy.dlou.edu.cn/8482/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "外国语与国际教育学院", "url": "https://wgy.dlou.edu.cn/xwdt/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "中新合作学院", "url": "https://zwhzbx.dlou.edu.cn/xwdt/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "马克思主义学院", "url": "https://mks.dlou.edu.cn/xyxw/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "应用技术学院", "url": "https://gzy.dlou.edu.cn/xyxw/list.htm", "category": "教学单位", "group": "教学单位"},
    {"name": "创新创业学院", "url": "https://cxcy.dlou.edu.cn/", "category": "教学单位", "group": "教学单位"},

    # ═══ 职能部门（人事处等） ═══
    {"name": "人事处·人才招聘", "url": "https://rsc.dlou.edu.cn/8821/list.htm", "category": "职能部门", "group": "职能部门"},
    {"name": "人事处·人事政策", "url": "https://rsc.dlou.edu.cn/8820/list.htm", "category": "职能部门", "group": "职能部门"},

    # ═══ 校园文化（校团委 · 共青团在线） ═══
    {"name": "团委·校园文化", "url": "https://tw.dlou.edu.cn/9692/list.htm", "category": "校园文化", "group": "校园文化"},
    {"name": "团委·通知公告", "url": "https://tw.dlou.edu.cn/9729/list.htm", "category": "校园文化", "group": "校园文化"},
    {"name": "团委·学院风采", "url": "https://tw.dlou.edu.cn/9693/list.htm", "category": "校园文化", "group": "校园文化"},
    {"name": "团委·社团风采", "url": "https://tw.dlou.edu.cn/9694/list.htm", "category": "校园文化", "group": "校园文化"},
]

# 分类组：顺序与官网首页 / 导航一致
CATEGORY_GROUPS = [
    ("📰 学校要闻", ["学校要闻"]),
    ("📢 通知公告", ["通知公告"]),
    ("🔬 学术科研", ["学术科研"]),
    ("🎓 人才培养", ["人才培养"]),
    ("🏫 教学单位", ["教学单位"]),
    ("🏛 职能部门", ["职能部门"]),
    ("🌊 校园文化", ["校园文化"]),
]

# 按 category 字段筛选（更稳）
CATEGORY_ORDER = ["学校要闻", "通知公告", "学术科研", "人才培养", "教学单位", "职能部门", "校园文化"]

GROUP_ICONS = {
    "学校要闻": "📰",
    "通知公告": "📢",
    "学术科研": "🔬",
    "人才培养": "🎓",
    "教学单位": "🏫",
    "职能部门": "🏛",
    "校园文化": "🌊",
}


def sources_by_category() -> dict[str, list[dict]]:
    """按 category 分组返回栏目，便于界面展示。"""
    buckets: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for s in SOURCES:
        buckets.setdefault(s["category"], []).append(s)
    return buckets


class Crawler:
    def __init__(
        self,
        max_workers: int = 20,
        max_articles_per_source: int = 15,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> None:
        # 防止非法并发参数直接打崩 ThreadPoolExecutor
        self.max_workers = max(1, min(int(max_workers or 1), 50))
        self.max_articles_per_source = max(1, min(int(max_articles_per_source or 1), 50))
        self.client = HttpClient(timeout=20)
        self._log = log_callback or (lambda msg: None)
        self._progress = progress_callback or (lambda done, total, msg: None)
        self.articles: list[Article] = []
        self.source_stats: list[dict] = []
        self._stop_flag = False

    def stop(self) -> None:
        """请求停止采集（协作式，进行中的单页会尽快结束）。"""
        self._stop_flag = True

    def _log_msg(self, msg: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log(f"[{timestamp}] {msg}")

    def _fetch_list(self, source: dict) -> list[dict]:
        if self._stop_flag:
            return []

        url = source["url"]
        name = source["name"]

        try:
            html = self.client.get(url, retries=2)
        except Exception as e:
            self._log_msg(f"列表页异常：{name} - {e}")
            return []

        if not html:
            self._log_msg(f"列表页访问失败：{name}")
            return []

        try:
            links = extract_list_links(html, url)
        except Exception as e:
            self._log_msg(f"列表解析失败：{name} - {e}")
            return []

        if not links:
            self._log_msg(f"未找到文章链接：{name}")
            return []

        for link in links:
            if not link.get("date"):
                link["date"] = date_from_url(link.get("url", ""))

        return links[: self.max_articles_per_source]

    def _fetch_article(self, link: dict, source: dict) -> Optional[Article]:
        if self._stop_flag:
            return None

        # 礼貌间隔：降低对目标站的瞬时压力
        try:
            import time as _time
            _time.sleep(0.05)
        except Exception:
            pass

        url = link.get("url", "")
        title = link.get("title", "")
        date = link.get("date")

        try:
            html = self.client.get(url, retries=2)
        except Exception:
            return None

        if not html:
            return None

        try:
            extracted = extract_article(html, url)
        except Exception:
            extracted = {"title": "", "content": "", "images": [], "attachments": []}

        article_title = clean_title(extracted.get("title") or title or "")
        content = extracted.get("content") or ""
        article_date = date or extracted.get("date")
        if not article_date and content:
            article_date = date_from_text(content)
        if not article_date and article_title:
            article_date = date_from_text(article_title)

        if not article_title or is_noise_title(article_title):
            return None

        # 过滤几乎没有正文的废文（提示信息/栏目壳）
        plain = strip_html(content)
        if len(plain.strip()) < 30:
            return None

        summary = ""
        try:
            from .html_tools import make_summary
            summary = make_summary(content)
        except Exception:
            pass

        return Article(
            title=article_title,
            url=url,
            category=source.get("category", ""),
            source=source.get("name", ""),
            date=article_date,
            content=content,
            images=extracted.get("images") or [],
            attachments=extracted.get("attachments") or [],
            summary=summary,
        )

    def crawl(self) -> list[Article]:
        """执行两阶段采集：先列表页，再文章页。返回按时间倒序的 Article 列表。"""
        self._stop_flag = False
        self.articles = []
        self.source_stats = []

        total_sources = len(SOURCES)
        self._log_msg("开始采集...")
        self._log_msg(f"共 {total_sources} 个栏目，并发线程 {self.max_workers}")
        self._progress(0, total_sources * 2, "抓取栏目列表…")

        all_links: list[tuple[dict, dict]] = []
        list_done = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_source = {executor.submit(self._fetch_list, s): s for s in SOURCES}

            for future in as_completed(future_to_source):
                source = future_to_source[future]
                list_done += 1
                self._progress(list_done, total_sources * 2, f"列表 {source['name']}")
                try:
                    links = future.result()
                    found = len(links) if links else 0
                    self.source_stats.append({
                        "name": source["name"],
                        "category": source["category"],
                        "url": source["url"],
                        "found": found,
                        "ok": 0,
                        "fail": 0,
                    })
                    if links:
                        self._log_msg(f"{source['name']}：找到 {found} 篇")
                        for link in links:
                            all_links.append((link, source))
                except Exception as e:
                    self._log_msg(f"{source['name']}：列表页异常 - {e}")
                    self.source_stats.append({
                        "name": source["name"],
                        "category": source["category"],
                        "url": source["url"],
                        "found": 0,
                        "ok": 0,
                        "fail": 0,
                        "error": str(e),
                    })

        if not all_links:
            self._log_msg("未找到任何文章链接")
            self._progress(total_sources * 2, total_sources * 2, "完成")
            return []

        # URL 去重
        seen_urls: set[str] = set()
        unique_links: list[tuple[dict, dict]] = []
        for link, source in all_links:
            u = link.get("url", "")
            if u and u not in seen_urls:
                seen_urls.add(u)
                unique_links.append((link, source))

        self._log_msg(f"共找到 {len(unique_links)} 篇文章（去重后），开始采集正文…")

        success_count = 0
        fail_count = 0
        art_done = 0
        art_total = len(unique_links)
        base = total_sources  # 进度条前半段

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_link = {
                executor.submit(self._fetch_article, link, source): (link, source)
                for link, source in unique_links
            }

            for future in as_completed(future_to_link):
                if self._stop_flag:
                    break

                link, source = future_to_link[future]
                art_done += 1
                self._progress(base + art_done, base + art_total, f"正文 {art_done}/{art_total}")

                try:
                    article = future.result()
                    if article and article.title:
                        self.articles.append(article)
                        success_count += 1
                        for st in self.source_stats:
                            if st["name"] == source["name"]:
                                st["ok"] += 1
                                break
                    else:
                        fail_count += 1
                        for st in self.source_stats:
                            if st["name"] == source["name"]:
                                st["fail"] += 1
                                break
                except Exception as e:
                    fail_count += 1
                    for st in self.source_stats:
                        if st["name"] == source["name"]:
                            st["fail"] += 1
                            break
                    self._log_msg(f"采集失败：{e}")

        self.articles.sort(key=lambda a: a.date or datetime.min, reverse=True)

        # 按分类汇总
        by_cat: dict[str, int] = {}
        for a in self.articles:
            by_cat[a.category] = by_cat.get(a.category, 0) + 1

        self._log_msg(f"采集完成：成功 {success_count} 篇，失败 {fail_count} 篇")
        for cat in CATEGORY_ORDER:
            if cat in by_cat:
                self._log_msg(f"  · {cat}：{by_cat[cat]} 篇")

        self._progress(base + art_total, base + art_total, "完成")
        return self.articles
