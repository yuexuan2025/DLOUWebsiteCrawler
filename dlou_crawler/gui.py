"""Tkinter 图形界面 — 布局稳定、按钮不乱、结果可筛选。"""
from __future__ import annotations

import os
import re
import sys
import threading
import webbrowser
from datetime import datetime
from tkinter import (
    Tk, Frame, Canvas, Scrollbar, Label, Text, Entry,
    Listbox, END, BOTH, LEFT, RIGHT, X, Y, WORD, DISABLED, NORMAL,
    StringVar, ttk, messagebox,
)

from .crawler import (
    Crawler, Article, CATEGORY_ORDER, GROUP_ICONS,
    SOURCES,
)
from .report import save_articles_json, save_articles_csv, export_web_report


def _get_output_dir() -> str:
    """输出目录：EXE 旁 output/；源码运行时为 源代码/output/。"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(os.path.dirname(sys.executable), "output")
    # 源代码/dlou_crawler/gui.py → 源代码/output
    source_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(source_root, "output")


# 统一按钮宽度（字符数），避免文字长短导致错位
BTN_W = 12
PAD_X = 8


class CrawlerGUI:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("DLOUWebsiteCrawler · 大连海洋大学官网采集器")
        self.root.geometry("1080x740")
        self.root.minsize(960, 640)
        self.root.configure(bg="#f1f5f9")

        self.crawler: Crawler | None = None
        self.articles: list[Article] = []
        self._filtered: list[Article] = []
        self._is_running = False
        self._selected_category = "全部"
        self._search_kw = ""

        self._setup_style()
        self._setup_ui()
        # 关窗时停止采集并确认
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        if self._is_running:
            if not messagebox.askyesno("确认退出", "正在采集中，确定要退出吗？"):
                return
            if self.crawler:
                self.crawler.stop()
        self.root.destroy()

    # ─────────── 样式 ───────────
    def _setup_style(self) -> None:
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure("App.TFrame", background="#f1f5f9")
        self.style.configure("Card.TFrame", background="#ffffff")
        self.style.configure("CardTitle.TLabel", background="#ffffff",
                             foreground="#0f172a", font=("Microsoft YaHei UI", 13, "bold"))
        self.style.configure("CardSub.TLabel", background="#ffffff",
                             foreground="#64748b", font=("Microsoft YaHei UI", 9))
        self.style.configure("Muted.TLabel", background="#f1f5f9",
                             foreground="#64748b", font=("Microsoft YaHei UI", 9))
        self.style.configure("Status.TLabel", background="#1d4ed8",
                             foreground="#bbf7d0", font=("Microsoft YaHei UI", 10, "bold"))

        self.style.configure("Primary.TButton",
                             background="#2563eb", foreground="#ffffff",
                             font=("Microsoft YaHei UI", 10, "bold"),
                             padding=(12, 8), borderwidth=0)
        self.style.map("Primary.TButton",
                       background=[("active", "#1d4ed8"), ("disabled", "#93c5fd")],
                       foreground=[("disabled", "#dbeafe")])

        self.style.configure("Danger.TButton",
                             background="#ef4444", foreground="#ffffff",
                             font=("Microsoft YaHei UI", 10, "bold"),
                             padding=(12, 8), borderwidth=0)
        self.style.map("Danger.TButton",
                       background=[("active", "#dc2626"), ("disabled", "#fca5a5")],
                       foreground=[("disabled", "#fee2e2")])

        self.style.configure("Ghost.TButton",
                             background="#e2e8f0", foreground="#0f172a",
                             font=("Microsoft YaHei UI", 10),
                             padding=(12, 8), borderwidth=0)
        self.style.map("Ghost.TButton", background=[("active", "#cbd5e1")])

        self.style.configure("Tab.TButton",
                             background="#ffffff", foreground="#475569",
                             font=("Microsoft YaHei UI", 9),
                             padding=(10, 6), borderwidth=1)
        self.style.map("Tab.TButton",
                       background=[("active", "#eff6ff")],
                       foreground=[("active", "#2563eb")])
        self.style.configure("TabActive.TButton",
                             background="#2563eb", foreground="#ffffff",
                             font=("Microsoft YaHei UI", 9, "bold"),
                             padding=(10, 6), borderwidth=0)
        self.style.map("TabActive.TButton",
                       background=[("active", "#1d4ed8")],
                       foreground=[("active", "#ffffff")])

    # ─────────── 总布局 ───────────
    def _setup_ui(self) -> None:
        # 顶部固定 Hero（不用滚动）
        self._build_hero()

        # 主体：可滚动
        body = Frame(self.root, bg="#f1f5f9")
        body.pack(fill=BOTH, expand=True)

        self._canvas = Canvas(body, bg="#f1f5f9", highlightthickness=0, bd=0)
        self._canvas.pack(side=LEFT, fill=BOTH, expand=True)

        vbar = Scrollbar(body, orient="vertical", command=self._canvas.yview)
        vbar.pack(side=RIGHT, fill=Y)
        self._canvas.configure(yscrollcommand=vbar.set)

        self._content = Frame(self._canvas, bg="#f1f5f9")
        self._content_window = self._canvas.create_window((0, 0), window=self._content, anchor="nw")

        self._content.bind("<Configure>", self._on_content_configure)
        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._build_controls()
        self._build_results()

    def _on_content_configure(self, _event=None) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_resize(self, event) -> None:
        self._canvas.itemconfigure(self._content_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        # 仅当鼠标在 canvas 上时滚动，避免抢走 Listbox/Text 的滚轮
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        if widget is None:
            return
        if widget is self._canvas or str(widget).startswith(str(self._content)):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ─────────── Hero ───────────
    def _build_hero(self) -> None:
        self._hero = Canvas(self.root, height=118, bg="#1d4ed8",
                            highlightthickness=0, bd=0)
        self._hero.pack(fill=X)

        self._hero.create_text(
            28, 32, text="DLOUWebsiteCrawler", fill="white",
            font=("Microsoft YaHei UI", 20, "bold"), anchor="w",
        )
        self._hero.create_text(
            28, 62, text="大连海洋大学官网采集器 · 对齐官网栏目分类", fill="#dbeafe",
            font=("Microsoft YaHei UI", 11), anchor="w",
        )
        self._hero.create_text(
            28, 88, text="学校要闻 · 通知公告 · 学术科研 · 人才培养 · 教学单位 · 职能部门 · 校园文化",
            fill="#bfdbfe", font=("Microsoft YaHei UI", 9), anchor="w",
        )

        self._status_label = Label(
            self._hero, text="●  就绪", fg="#86efac", bg="#1d4ed8",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self._status_label.place(relx=1.0, x=-28, y=28, anchor="ne")

        self._hero_progress = ttk.Progressbar(
            self._hero, orient="horizontal", length=280, mode="determinate",
        )
        self._hero_progress.place(relx=1.0, x=-28, y=58, anchor="ne")

        self._progress_label = Label(
            self._hero, text="", fg="#dbeafe", bg="#1d4ed8",
            font=("Microsoft YaHei UI", 9),
        )
        self._progress_label.place(relx=1.0, x=-28, y=88, anchor="ne")

        self._draw_gradient(1200)

    def _draw_gradient(self, width: int) -> None:
        self._hero.delete("gradient")
        w = max(width, 200)
        # 左 #1d4ed8 → 右 #3730a3
        for i in range(w):
            t = i / w
            r = int(29 + (55 - 29) * t)
            g = int(78 + (48 - 78) * t)
            b = int(216 + (163 - 216) * t)
            self._hero.create_line(i, 0, i, 118, fill=f"#{r:02x}{g:02x}{b:02x}", tags="gradient")
        self._hero.tag_lower("gradient")

    # ─────────── 控制区 ───────────
    def _build_controls(self) -> None:
        wrap = Frame(self._content, bg="#f1f5f9")
        wrap.pack(fill=X, padx=20, pady=(16, 8))

        # 用 grid 固定列宽，按钮不会错位
        card = Frame(wrap, bg="#ffffff", highlightthickness=1, highlightbackground="#e2e8f0")
        card.pack(fill=X)

        inner = Frame(card, bg="#ffffff")
        inner.pack(fill=X, padx=16, pady=14)
        inner.columnconfigure(0, weight=1)
        inner.columnconfigure(1, weight=0)

        # 左：标题 + 说明
        left = Frame(inner, bg="#ffffff")
        left.grid(row=0, column=0, sticky="w")

        Label(left, text="采集控制", bg="#ffffff", fg="#0f172a",
              font=("Microsoft YaHei UI", 13, "bold")).pack(anchor="w")

        self._info_var = StringVar(
            value=f"栏目 {len(SOURCES)} 个  ·  分类 {len(CATEGORY_ORDER)} 组  ·  默认并发 20  ·  每栏最多 15 篇"
        )
        Label(left, textvariable=self._info_var, bg="#ffffff", fg="#64748b",
              font=("Microsoft YaHei UI", 9)).pack(anchor="w", pady=(4, 0))

        # 右：按钮组 — 固定宽度 + 统一 pack
        right = Frame(inner, bg="#ffffff")
        right.grid(row=0, column=1, sticky="e")

        self._start_btn = ttk.Button(
            right, text="开始采集", command=self._on_start,
            style="Primary.TButton", width=BTN_W,
        )
        self._start_btn.pack(side=LEFT, padx=(0, PAD_X))

        self._stop_btn = ttk.Button(
            right, text="停止", command=self._on_stop,
            style="Danger.TButton", width=BTN_W, state=DISABLED,
        )
        self._stop_btn.pack(side=LEFT, padx=(0, PAD_X))

        self._report_btn = ttk.Button(
            right, text="打开报告", command=self._on_open_report,
            style="Ghost.TButton", width=BTN_W,
        )
        self._report_btn.pack(side=LEFT, padx=(0, PAD_X))

        self._img_btn = ttk.Button(
            right, text="查看图片", command=self._on_preview_images,
            style="Ghost.TButton", width=BTN_W,
        )
        self._img_btn.pack(side=LEFT)

        # 第二行：日志 + 栏目统计
        mid = Frame(card, bg="#ffffff")
        mid.pack(fill=X, padx=16, pady=(0, 14))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)

        log_frame = Frame(mid, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        Label(log_frame, text="运行日志", bg="#f8fafc", fg="#334155",
              font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 4))

        self._log_text = Text(log_frame, height=8, bg="#f8fafc", fg="#334155",
                              font=("Consolas", 9), relief="flat", wrap=WORD,
                              padx=10, pady=6)
        self._log_text.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))

        stats_frame = Frame(mid, bg="#f8fafc", highlightthickness=1, highlightbackground="#e2e8f0")
        stats_frame.grid(row=0, column=1, sticky="nsew")

        Label(stats_frame, text="栏目一览", bg="#f8fafc", fg="#334155",
              font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 4))

        self._stats_text = Text(stats_frame, height=8, bg="#f8fafc", fg="#475569",
                                font=("Microsoft YaHei UI", 9), relief="flat", wrap=WORD,
                                padx=10, pady=6)
        self._stats_text.pack(fill=BOTH, expand=True, padx=8, pady=(0, 8))
        self._fill_source_stats()

        self._log("欢迎使用 DLOUWebsiteCrawler 大连海洋大学官网采集器")
        self._log(f"已加载 {len(SOURCES)} 个采集栏目（对齐官网分类）")
        self._log("点击「开始采集」开始抓取公开信息")

    def _fill_source_stats(self) -> None:
        self._stats_text.configure(state=NORMAL)
        self._stats_text.delete("1.0", END)
        for cat in CATEGORY_ORDER:
            icon = GROUP_ICONS.get(cat, "•")
            n = sum(1 for s in SOURCES if s["category"] == cat)
            self._stats_text.insert(END, f"{icon} {cat}（{n}）\n")
            names = [s["name"] for s in SOURCES if s["category"] == cat]
            self._stats_text.insert(END, "   " + "、".join(names[:4]))
            if len(names) > 4:
                self._stats_text.insert(END, f" 等 {len(names)} 项")
            self._stats_text.insert(END, "\n")
        self._stats_text.configure(state=DISABLED)

    # ─────────── 结果区 ───────────
    def _build_results(self) -> None:
        card = Frame(self._content, bg="#ffffff", highlightthickness=1,
                     highlightbackground="#e2e8f0")
        card.pack(fill=BOTH, expand=True, padx=20, pady=(8, 20))

        # 工具栏：搜索 + 计数
        toolbar = Frame(card, bg="#ffffff")
        toolbar.pack(fill=X, padx=16, pady=(14, 8))

        Label(toolbar, text="采集结果", bg="#ffffff", fg="#0f172a",
              font=("Microsoft YaHei UI", 13, "bold")).pack(side=LEFT)

        self._count_var = StringVar(value="0 篇")
        Label(toolbar, textvariable=self._count_var, bg="#ffffff", fg="#64748b",
              font=("Microsoft YaHei UI", 10)).pack(side=RIGHT)

        # 分类 Tab
        tabs = Frame(card, bg="#ffffff")
        tabs.pack(fill=X, padx=16, pady=(4, 8))

        self._tab_buttons: list[tuple[ttk.Button, str]] = []
        cats = ["全部"] + [f"{GROUP_ICONS.get(c, '')} {c}" for c in CATEGORY_ORDER]
        for cat in cats:
            btn = ttk.Button(tabs, text=cat, style="Tab.TButton",
                             command=lambda c=cat: self._on_category_change(c))
            btn.pack(side=LEFT, padx=(0, 6))
            self._tab_buttons.append((btn, cat))

        # 搜索行
        search_row = Frame(card, bg="#ffffff")
        search_row.pack(fill=X, padx=16, pady=(0, 8))

        Label(search_row, text="搜索", bg="#ffffff", fg="#64748b",
              font=("Microsoft YaHei UI", 9)).pack(side=LEFT, padx=(0, 6))

        self._search_var = StringVar()
        self._search_entry = Entry(search_row, textvariable=self._search_var,
                                   font=("Microsoft YaHei UI", 10), relief="flat",
                                   bg="#f8fafc", fg="#0f172a")
        self._search_entry.pack(side=LEFT, fill=X, expand=True, ipady=6)
        self._search_entry.bind("<KeyRelease>", lambda e: self._on_search())

        ttk.Button(search_row, text="清空", style="Ghost.TButton", width=8,
                   command=self._clear_search).pack(side=LEFT, padx=(8, 0))

        # 列表 + 详情
        paned = Frame(card, bg="#ffffff")
        paned.pack(fill=BOTH, expand=True, padx=16, pady=(0, 14))
        paned.columnconfigure(0, weight=1)
        paned.columnconfigure(1, weight=1)
        paned.rowconfigure(0, weight=1)

        # 左：列表
        left = Frame(paned, bg="#ffffff")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        Label(left, text="文章列表", bg="#ffffff", fg="#334155",
              font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(0, 4))

        list_box = Frame(left, bg="#f8fafc", highlightthickness=1,
                         highlightbackground="#e2e8f0")
        list_box.pack(fill=BOTH, expand=True)

        self._article_listbox = Listbox(
            list_box, bg="#ffffff", fg="#1e293b",
            font=("Microsoft YaHei UI", 9),
            relief="flat", bd=0, highlightthickness=0,
            selectbackground="#dbeafe", selectforeground="#1d4ed8",
            activestyle="none", exportselection=False,
        )
        self._article_listbox.pack(side=LEFT, fill=BOTH, expand=True, padx=1, pady=1)
        self._article_listbox.bind("<<ListboxSelect>>", self._on_article_select)

        sb = Scrollbar(list_box, orient="vertical", command=self._article_listbox.yview)
        sb.pack(side=RIGHT, fill=Y)
        self._article_listbox.configure(yscrollcommand=sb.set)

        # 右：详情
        right = Frame(paned, bg="#ffffff")
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        Label(right, text="文章预览", bg="#ffffff", fg="#334155",
              font=("Microsoft YaHei UI", 10, "bold")).pack(anchor="w", pady=(0, 4))

        self._detail_title = Label(right, text="请选择左侧文章查看详情",
                                   bg="#ffffff", fg="#0f172a",
                                   font=("Microsoft YaHei UI", 11, "bold"),
                                   wraplength=420, justify="left")
        self._detail_title.pack(fill=X, pady=(0, 4))

        self._detail_meta = Label(right, text="", bg="#ffffff", fg="#64748b",
                                  font=("Microsoft YaHei UI", 9), justify="left")
        self._detail_meta.pack(fill=X, pady=(0, 6))

        detail_box = Frame(right, bg="#f8fafc", highlightthickness=1,
                           highlightbackground="#e2e8f0")
        detail_box.pack(fill=BOTH, expand=True)

        self._detail_text = Text(detail_box, bg="#ffffff", fg="#334155",
                                 font=("Microsoft YaHei UI", 9),
                                 relief="flat", wrap=WORD, padx=10, pady=8)
        self._detail_text.pack(side=LEFT, fill=BOTH, expand=True, padx=1, pady=1)

        dsb = Scrollbar(detail_box, orient="vertical", command=self._detail_text.yview)
        dsb.pack(side=RIGHT, fill=Y)
        self._detail_text.configure(yscrollcommand=dsb.set, state=DISABLED)

        # 底部：原文 / 打开图片
        link_row = Frame(right, bg="#ffffff")
        link_row.pack(fill=X, pady=(6, 0))

        self._detail_link = Label(link_row, text="", bg="#ffffff", fg="#2563eb",
                                  font=("Microsoft YaHei UI", 9), cursor="hand2")
        self._detail_link.pack(side=LEFT)
        self._detail_link.bind("<Button-1>", self._open_current_url)

        self._img_link = Label(link_row, text="", bg="#ffffff", fg="#2563eb",
                               font=("Microsoft YaHei UI", 9), cursor="hand2")
        self._img_link.pack(side=LEFT, padx=(16, 0))
        self._img_link.bind("<Button-1>", self._open_current_image)

        self._current_url = ""
        self._current_images: list = []
        self._refresh_tabs()

    # ─────────── 日志 ───────────
    def _log(self, msg: str) -> None:
        def _append() -> None:
            ts = datetime.now().strftime("%H:%M:%S")
            self._log_text.insert(END, f"[{ts}] {msg}\n")
            self._log_text.see(END)
        try:
            self.root.after(0, _append)
        except Exception:
            pass

    def _set_progress(self, done: int, total: int, msg: str) -> None:
        def _update() -> None:
            try:
                self._hero_progress["maximum"] = max(total, 1)
                self._hero_progress["value"] = done
                self._progress_label.configure(text=msg)
            except Exception:
                pass
        try:
            self.root.after(0, _update)
        except Exception:
            pass

    # ─────────── 采集控制 ───────────
    def _on_start(self) -> None:
        if self._is_running:
            return

        self._is_running = True
        self._start_btn.configure(state=DISABLED)
        self._stop_btn.configure(state=NORMAL)
        self._status_label.configure(text="●  采集中…", fg="#fde68a")
        self._log("开始采集…")

        t = threading.Thread(target=self._run_crawler, daemon=True)
        t.start()

    def _on_stop(self) -> None:
        if self.crawler:
            self.crawler.stop()
            self._log("正在停止…")
            self._status_label.configure(text="●  正在停止…", fg="#fca5a5")

    def _run_crawler(self) -> None:
        try:
            self.crawler = Crawler(
                max_workers=20,
                max_articles_per_source=15,
                log_callback=self._log,
                progress_callback=self._set_progress,
            )
            self.articles = self.crawler.crawl()
            self.root.after(0, self._on_crawl_done)
        except Exception as e:
            self._log(f"采集异常：{e}")
            self.root.after(0, self._on_crawl_done)

    def _on_crawl_done(self) -> None:
        self._is_running = False
        self._start_btn.configure(state=NORMAL)
        self._stop_btn.configure(state=DISABLED)
        self._status_label.configure(text="●  就绪", fg="#86efac")
        self._progress_label.configure(text="")

        if self.articles:
            self._show_results()
            self._export_outputs()
        else:
            self._log("未采集到任何文章")

    def _export_outputs(self) -> None:
        try:
            output_dir = _get_output_dir()
            os.makedirs(output_dir, exist_ok=True)
            json_path = os.path.join(output_dir, "articles.json")
            save_articles_json(self.articles, json_path)
            csv_path = os.path.join(output_dir, "articles.csv")
            save_articles_csv(self.articles, csv_path)
            report_path = export_web_report(
                self.articles, output_dir, getattr(self.crawler, "source_stats", None)
            )
            self._log(f"数据已生成：{json_path}")
            self._log(f"表格已生成：{csv_path}")
            self._log(f"报告已生成：{report_path}")
        except Exception as e:
            self._log(f"导出失败：{e}")

    # ─────────── 结果展示 ───────────
    def _show_results(self) -> None:
        self._apply_filter()

    def _refresh_tabs(self) -> None:
        # 视觉高亮当前 Tab
        for btn, cat in self._tab_buttons:
            is_active = (
                cat == self._selected_category
                or (self._selected_category != "全部" and cat.endswith(self._selected_category))
            )
            try:
                btn.configure(style="TabActive.TButton" if is_active else "Tab.TButton")
            except Exception:
                pass

    def _on_category_change(self, cat: str) -> None:
        # cat 形如 "📰 学校要闻" 或 "全部"
        if cat == "全部":
            self._selected_category = "全部"
        else:
            # 去掉图标前缀
            self._selected_category = cat.split(" ", 1)[-1] if " " in cat else cat
        self._refresh_tabs()
        self._clear_detail()
        self._apply_filter()

    def _on_search(self) -> None:
        self._search_kw = self._search_var.get().strip()
        self._apply_filter()

    def _clear_search(self) -> None:
        self._search_var.set("")
        self._search_kw = ""
        self._apply_filter()

    def _apply_filter(self) -> None:
        items = list(self.articles)

        if self._selected_category != "全部":
            items = [a for a in items if a.category == self._selected_category]

        if self._search_kw:
            kw = self._search_kw.lower()
            items = [
                a for a in items
                if kw in (a.title or "").lower()
                or kw in (a.content or "").lower()
                or kw in (a.source or "").lower()
                or kw in (getattr(a, "summary", "") or "").lower()
            ]

        self._filtered = items
        self._count_var.set(f"{len(items)} 篇")

        self._article_listbox.delete(0, END)
        for a in items:
            d = a.date.strftime("%m-%d") if a.date else "----"
            title = a.title or "（无标题）"
            if len(title) > 28:
                title = title[:27] + "…"
            n_img = len(a.images or [])
            n_att = len(a.attachments or [])
            flags = []
            if n_img:
                flags.append(f"{n_img}图")
            if n_att:
                flags.append(f"{n_att}附")
            flag_s = (" [" + ",".join(flags) + "]") if flags else ""
            self._article_listbox.insert(END, f" {d} {title}{flag_s}  ·{a.source}")

    def _on_article_select(self, _event=None) -> None:
        sel = self._article_listbox.curselection()
        if not sel or not self._filtered:
            return
        idx = sel[0]
        if idx >= len(self._filtered):
            return
        a = self._filtered[idx]
        self._show_detail(a)

    def _show_detail(self, a: Article) -> None:
        self._current_url = a.url or ""
        self._current_images = list(a.images or [])
        self._detail_title.configure(text=a.title or "（无标题）")

        d = a.date.strftime("%Y-%m-%d") if a.date else "未知日期"
        parts = [f"来源：{a.source}", f"分类：{a.category}", f"时间：{d}"]
        if a.images:
            parts.append(f"{len(a.images)} 图")
        if a.attachments:
            parts.append(f"{len(a.attachments)} 附件")
        self._detail_meta.configure(text="  |  ".join(parts))

        # 正文（去标签）
        content = a.content or "暂无正文内容"
        content = re.sub(r"<img[^>]*>", "\n[图片]\n", content)
        content = re.sub(r"</p>|<br\s*/?>|</li>|</h[1-6]>", "\n", content)
        content = re.sub(r"<[^>]+>", "", content)
        content = content.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
        content = re.sub(r"\n{3,}", "\n\n", content).strip()

        blocks = [content]
        imgs = a.images or []
        if imgs:
            blocks.append("—— 图片（点右上「打开图片」预览）——")
            for i, img in enumerate(imgs[:30], 1):
                alt = (img.get("alt") or "").strip()
                blocks.append(f"[{i}] {alt or '图片'}\n    {img.get('src','')}")
        atts = a.attachments or []
        if atts:
            blocks.append("—— 附件 ——")
            for i, att in enumerate(atts, 1):
                blocks.append(f"[{i}] {att.get('name','')}\n    {att.get('url','')}")

        self._detail_text.configure(state=NORMAL)
        self._detail_text.delete("1.0", END)
        self._detail_text.insert("1.0", "\n\n".join(blocks))
        self._detail_text.configure(state=DISABLED)

        self._detail_link.configure(text="在浏览器中打开原文 ↗" if a.url else "")
        self._img_link.configure(text="打开图片 ↗" if self._current_images else "")

    def _open_current_image(self, _event=None) -> None:
        if not getattr(self, "_current_images", None):
            return
        src = (self._current_images[0] or {}).get("src") or ""
        if src:
            try:
                webbrowser.open(src)
            except Exception:
                pass

    def _clear_detail(self) -> None:
        self._current_url = ""
        self._current_images = []
        self._detail_title.configure(text="请选择左侧文章查看详情")
        self._detail_meta.configure(text="")
        self._detail_text.configure(state=NORMAL)
        self._detail_text.delete("1.0", END)
        self._detail_text.configure(state=DISABLED)
        self._detail_link.configure(text="")
        self._img_link.configure(text="")

    def _open_current_url(self, _event=None) -> None:
        if self._current_url:
            try:
                webbrowser.open(self._current_url)
            except Exception:
                pass

    # ─────────── 打开报告 ───────────
    def _on_open_report(self) -> None:
        """优先打开带 data.js 的 output/index.html。"""
        candidates = [
            os.path.join(_get_output_dir(), "index.html"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "index.html"),
        ]
        # 优先完整报告（旁边有 data.js）
        for html_path in candidates:
            if os.path.isfile(html_path) and os.path.isfile(os.path.join(os.path.dirname(html_path), "data.js")):
                webbrowser.open("file:///" + html_path.replace("\\", "/"))
                return
        for html_path in candidates:
            if os.path.isfile(html_path):
                webbrowser.open("file:///" + html_path.replace("\\", "/"))
                return
        messagebox.showinfo("提示", "报告尚未生成，请先点击「开始采集」")

    def _on_preview_images(self) -> None:
        imgs = list(getattr(self, "_current_images", None) or [])
        if not imgs:
            messagebox.showinfo("提示", "请先在左侧选择一篇带图片的文章")
            return
        self._show_image_window(imgs)

    def _show_image_window(self, imgs: list) -> None:
        from tkinter import Toplevel

        win = Toplevel(self.root)
        win.title(f"图片预览（{len(imgs)} 张）")
        win.configure(bg="#f8fafc")
        win.geometry("720x560")

        state = {"i": 0, "photo": None}
        header = Frame(win, bg="#f8fafc")
        header.pack(fill=X, padx=12, pady=8)
        counter = Label(header, text="", bg="#f8fafc", fg="#64748b",
                        font=("Microsoft YaHei UI", 10))
        counter.pack(side=LEFT)
        btn_box = Frame(header, bg="#f8fafc")
        btn_box.pack(side=RIGHT)
        canvas = Canvas(win, bg="#e2e8f0", highlightthickness=0)
        canvas.pack(fill=BOTH, expand=True, padx=12, pady=(0, 12))

        def load(idx: int) -> None:
            idx = max(0, min(idx, len(imgs) - 1))
            state["i"] = idx
            src = (imgs[idx] or {}).get("src") or ""
            counter.configure(text=f"{idx + 1} / {len(imgs)}  加载中…")
            canvas.delete("all")
            if not src:
                counter.configure(text=f"{idx + 1} / {len(imgs)}  无有效地址")
                return

            def worker():
                photo = self._load_photo(src)
                def apply():
                    if photo is not None:
                        state["photo"] = photo
                        w = max(canvas.winfo_width(), 600)
                        h = max(canvas.winfo_height(), 400)
                        canvas.delete("all")
                        canvas.create_image(w // 2, h // 2, image=photo, anchor="center")
                        counter.configure(text=f"{idx + 1} / {len(imgs)}")
                    else:
                        counter.configure(text=f"{idx + 1} / {len(imgs)}  加载失败")
                win.after(0, apply)

            threading.Thread(target=worker, daemon=True).start()

        def open_browser():
            src = (imgs[state["i"]] or {}).get("src") or ""
            if src:
                try:
                    webbrowser.open(src)
                except Exception:
                    pass

        ttk.Button(btn_box, text="上一张", style="Ghost.TButton", width=8,
                   command=lambda: load(state["i"] - 1)).pack(side=LEFT, padx=4)
        ttk.Button(btn_box, text="下一张", style="Ghost.TButton", width=8,
                   command=lambda: load(state["i"] + 1)).pack(side=LEFT, padx=4)
        ttk.Button(btn_box, text="浏览器打开", style="Ghost.TButton", width=10,
                   command=open_browser).pack(side=LEFT, padx=4)

        win.after(80, lambda: load(0))

    def _load_photo(self, src: str):
        try:
            import urllib.request
            req = urllib.request.Request(
                src,
                headers={"User-Agent": "Mozilla/5.0 (compatible; DLOUCrawler/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read(8 * 1024 * 1024)
        except Exception:
            return None
        try:
            import io
            from PIL import Image, ImageTk
            im = Image.open(io.BytesIO(data))
            im.thumbnail((680, 500))
            return ImageTk.PhotoImage(im)
        except Exception:
            pass
        try:
            import base64
            import tkinter as _tk
            return _tk.PhotoImage(data=base64.b64encode(data))
        except Exception:
            return None
