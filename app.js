/* DLOUWebsiteCrawler 采集报告 · 唯一前端 */
(function () {
  "use strict";

  const data = window.__DLOU__ || null;
  const articles = (data && data.articles) || [];
  const CATEGORY_ORDER = (data && data.categories) || [
    "学校要闻", "通知公告", "学术科研", "人才培养", "教学单位", "职能部门", "校园文化",
  ];
  const CATEGORY_LABELS = (data && data.category_icons) || {};
  const SOURCES = (data && data.sources) || [];

  let currentCategory = "all";
  let currentSort = "date-desc";
  let currentSearch = "";

  const $ = (sel) => document.querySelector(sel);
  const articleContainer = $("#articleContainer");
  const resultCount = $("#resultCount");
  const categoryTabs = $("#categoryTabs");
  const drawer = $("#drawer");
  const drawerMask = $("#drawerMask");
  const lightbox = $("#lightbox");
  const lightboxImg = $("#lightboxImg");

  // ── 工具 ──
  function escapeHtml(str) {
    return String(str ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function escapeAttr(str) {
    return escapeHtml(str).replace(/'/g, "&#39;");
  }
  function safeUrl(url) {
    const u = String(url || "").trim();
    if (!u) return "";
    const low = u.toLowerCase();
    if (low.startsWith("javascript:") || low.startsWith("data:") || low.startsWith("vbscript:") || low.startsWith("file:")) {
      return "";
    }
    return u;
  }
  function stripHtml(html) {
    return String(html ?? "").replace(/<[^>]+>/g, " ");
  }
  function catLabel(cat) {
    const icon = CATEGORY_LABELS[cat] || "";
    return icon ? icon + " " + cat : cat;
  }
  function dateKey(d) {
    if (!d) return 0;
    const t = Date.parse(String(d).replace(/\//g, "-"));
    return Number.isNaN(t) ? 0 : t;
  }

  // ── 统计 / 栏目 ──
  function updateStats() {
    const imgs = articles.reduce((n, a) => n + (a.images || []).length, 0);
    const files = articles.reduce((n, a) => n + (a.attachments || []).length, 0);
    $("#statArticles").textContent = String(articles.length);
    $("#statImages").textContent = String(imgs);
    $("#statFiles").textContent = String(files);
    $("#statSources").textContent = String(SOURCES.length || "—");
    if (data && data.generated_at) {
      $("#genTime").textContent = "生成时间：" + data.generated_at;
    }
  }

  function renderSources() {
    const grid = $("#sourceGrid");
    if (!grid) return;
    grid.innerHTML = "";
    const byCat = {};
    SOURCES.forEach((s) => {
      (byCat[s.category] = byCat[s.category] || []).push(s);
    });
    CATEGORY_ORDER.forEach((cat) => {
      const items = byCat[cat] || [];
      if (!items.length) return;
      const card = document.createElement("article");
      card.className = "source-card";
      card.innerHTML = `
        <div class="source-card-head">
          <div class="source-icon">${escapeHtml(CATEGORY_LABELS[cat] || "•")}</div>
          <span class="source-count">${items.length} 栏</span>
        </div>
        <h3>${escapeHtml(cat)}</h3>
        <div class="source-tags">
          ${items.map((it) => `<span class="tag">${escapeHtml(it.name)}</span>`).join("")}
        </div>`;
      grid.appendChild(card);
    });
  }

  function renderTabs() {
    categoryTabs.querySelectorAll(".tab-btn:not([data-category='all'])").forEach((t) => t.remove());
    CATEGORY_ORDER.forEach((cat) => {
      const btn = document.createElement("button");
      btn.className = "tab-btn";
      btn.dataset.category = cat;
      btn.textContent = catLabel(cat);
      categoryTabs.appendChild(btn);
    });
  }

  // ── 过滤 ──
  function getFiltered() {
    let list = [...articles];
    if (currentCategory !== "all") {
      list = list.filter((a) => a.category === currentCategory);
    }
    if (currentSearch) {
      const q = currentSearch.toLowerCase();
      list = list.filter(
        (a) =>
          (a.title || "").toLowerCase().includes(q) ||
          (a.summary || "").toLowerCase().includes(q) ||
          stripHtml(a.content || "").toLowerCase().includes(q) ||
          (a.source || "").toLowerCase().includes(q)
      );
    }
    switch (currentSort) {
      case "date-asc":
        list.sort((a, b) => dateKey(a.date) - dateKey(b.date));
        break;
      case "title-asc":
        list.sort((a, b) => (a.title || "").localeCompare(b.title || "", "zh-CN"));
        break;
      case "img-first":
        list.sort((a, b) => {
          const ia = (a.images || []).length > 0 ? 1 : 0;
          const ib = (b.images || []).length > 0 ? 1 : 0;
          if (ia !== ib) return ib - ia;
          return dateKey(b.date) - dateKey(a.date);
        });
        break;
      default:
        list.sort((a, b) => dateKey(b.date) - dateKey(a.date));
    }
    return list;
  }

  // ── 列表（带缩略图） ──
  function renderArticles() {
    const filtered = getFiltered();
    resultCount.textContent = filtered.length + " 篇";

    if (!filtered.length) {
      articleContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <p>${articles.length ? "没有匹配的文章" : "暂无采集数据"}</p>
          <p class="empty-hint">${articles.length ? "换个关键词或分类试试" : "运行 <code>python run_cli.py</code> 后刷新"}</p>
        </div>`;
      return;
    }

    const frag = document.createDocumentFragment();
    filtered.forEach((a, i) => {
      const imgs = a.images || [];
      const cover = imgs[0] && safeUrl(imgs[0].src);
      const el = document.createElement("article");
      el.className = "article-item" + (cover ? " has-cover" : "");
      el.style.animationDelay = Math.min(i, 16) * 0.025 + "s";
      el.innerHTML = `
        ${cover ? `<div class="thumb"><img src="${escapeAttr(cover)}" alt="" loading="lazy"></div>` : ""}
        <div class="article-body">
          <div class="article-top">
            <div class="article-title">${escapeHtml(a.title || "（无标题）")}</div>
            <div class="article-date">${escapeHtml(a.date || "")}</div>
          </div>
          ${a.summary ? `<p class="article-summary">${escapeHtml(a.summary)}</p>` : ""}
          <div class="article-meta">
            <span class="badge badge-source">${escapeHtml(a.source || "")}</span>
            <span class="badge badge-soft">${escapeHtml(a.category || "")}</span>
            ${imgs.length ? `<span class="meta-item">🖼 ${imgs.length}</span>` : ""}
            ${(a.attachments || []).length ? `<span class="meta-item">📎 ${(a.attachments || []).length}</span>` : ""}
          </div>
        </div>`;
      el.addEventListener("click", () => openDrawer(a));
      frag.appendChild(el);
    });
    articleContainer.innerHTML = "";
    articleContainer.appendChild(frag);
  }

  // ── 详情 + 图集 ──
  function openDrawer(a) {
    $("#drawerTitle").textContent = a.title || "（无标题）";
    $("#drawerMeta").innerHTML = `
      <span class="badge badge-source">${escapeHtml(a.source || "")}</span>
      <span class="badge badge-soft">${escapeHtml(a.date || "未知日期")}</span>
      <span class="badge badge-soft">${escapeHtml(a.category || "")}</span>`;

    // 正文：保留安全 HTML，并把 img 转成灯箱
    const body = $("#drawerBody");
    body.innerHTML = a.content || "<p>暂无正文</p>";
    body.querySelectorAll("img").forEach((img) => {
      img.style.cursor = "zoom-in";
      img.addEventListener("click", () => openLightbox(img.src));
    });

    // 图集
    const gallery = $("#drawerGallery");
    const imgs = (a.images || []).filter((im) => safeUrl(im.src));
    gallery.innerHTML = imgs.length
      ? `<h4>图片（${imgs.length}）</h4><div class="gallery">` +
        imgs
          .map(
            (im) =>
              `<button class="gallery-item" data-src="${escapeAttr(safeUrl(im.src))}">` +
              `<img src="${escapeAttr(safeUrl(im.src))}" alt="${escapeAttr(im.alt || "")}" loading="lazy">` +
              `</button>`
          )
          .join("") +
        `</div>`
      : "";
    gallery.querySelectorAll(".gallery-item").forEach((btn) => {
      btn.addEventListener("click", () => openLightbox(btn.dataset.src));
    });

    // 附件 + 原文
    const atts = (a.attachments || []).filter((at) => safeUrl(at.url));
    $("#drawerFooter").innerHTML =
      (safeUrl(a.url)
        ? `<a class="origin-link" href="${escapeAttr(safeUrl(a.url))}" target="_blank" rel="noopener noreferrer">查看官网原文 ↗</a>`
        : "") +
      atts
        .map(
          (at) =>
            `<a class="att-item" href="${escapeAttr(safeUrl(at.url))}" target="_blank" rel="noopener noreferrer">📎 ${escapeHtml(at.name || "附件")}</a>`
        )
        .join("");

    drawer.hidden = false;
    drawerMask.hidden = false;
    drawer.setAttribute("aria-hidden", "false");
    requestAnimationFrame(() => drawer.classList.add("open"));
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    setTimeout(() => {
      drawer.hidden = true;
      drawerMask.hidden = true;
    }, 260);
  }

  function openLightbox(src) {
    const u = safeUrl(src);
    if (!u) return;
    lightboxImg.src = u;
    lightbox.hidden = false;
  }
  function closeLightbox() {
    lightbox.hidden = true;
    lightboxImg.src = "";
  }

  // ── 启动 ──
  function init() {
    updateStats();
    renderSources();
    renderTabs();
    renderArticles();

    $("#searchInput").addEventListener("input", (e) => {
      currentSearch = e.target.value.trim();
      renderArticles();
    });
    $("#sortSelect").addEventListener("change", (e) => {
      currentSort = e.target.value;
      renderArticles();
    });
    categoryTabs.addEventListener("click", (e) => {
      const btn = e.target.closest(".tab-btn");
      if (!btn) return;
      currentCategory = btn.dataset.category;
      categoryTabs.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderArticles();
    });
    $("#drawerClose").addEventListener("click", closeDrawer);
    drawerMask.addEventListener("click", closeDrawer);
    $("#lightboxClose").addEventListener("click", closeLightbox);
    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) closeLightbox();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!lightbox.hidden) closeLightbox();
        else if (!drawer.hidden) closeDrawer();
      }
    });
  }

  init();
})();
