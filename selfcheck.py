"""轻量自检：python selfcheck.py"""
from __future__ import annotations

import ast
import tempfile
import pathlib
import sys

SRC_ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(SRC_ROOT))


def main() -> int:
    print("== 语法 ==")
    for p in list((SRC_ROOT / "dlou_crawler").glob("*.py")) + [SRC_ROOT / "run.py", SRC_ROOT / "run_cli.py"]:
        ast.parse(p.read_text(encoding="utf-8"))
        print("  OK", p.name)

    print("== 导入 / 规则 ==")
    from dlou_crawler.html_tools import (
        clean_title, is_noise_title, is_attachment, extract_article,
        date_from_text, is_article_link,
    )
    from dlou_crawler.report import sanitize_html, save_articles_csv, export_web_report, _safe_url
    from dlou_crawler.crawler import Crawler, Article, SOURCES, CATEGORY_ORDER
    from dlou_crawler.client import is_allowed_url

    assert clean_title("[04-30]标题 - 大连海洋大学") == "标题"
    assert clean_title("关于进一步规范工作的通知 2025-01-20") == "关于进一步规范工作的通知"
    assert clean_title("关于进一步规范工作的通知[2025-01-20]") == "关于进一步规范工作的通知"
    assert clean_title("关于进一步规范工作的通知 2025年1月20日") == "关于进一步规范工作的通知"
    assert is_noise_title("提示信息") and is_noise_title("联系我们")
    assert not is_noise_title("学校召开运动会")
    assert not is_noise_title("喜报") and not is_noise_title("公示") and not is_noise_title("通知")
    assert is_attachment("a.zip", "公示") and not is_attachment("a/list.htm", "下载专区")

    # 现网 URL：/YYYY/MMDD/cXXXaNNNN/page.htm
    assert is_article_link(
        "https://news.dlou.edu.cn/2026/0927/c1281a208763/page.htm",
        "关于进一步规范工作的通知",
    )
    assert is_article_link(
        "https://life.dlou.edu.cn/2025/0119/c89a185975/page.htm",
        "水产与生命学院新闻",
    )
    assert not is_article_link("https://news.dlou.edu.cn/1281/list.htm", "学校要闻")

    # 噪声标题回退：详情页「提示信息」不丢文，应用列表标题
    from dlou_crawler.client import is_blocked_page
    tip_html = (
        "<html><head><title>提示信息</title></head><body>"
        "<p>提示：您当前ip并非校内地址，该信息仅允许校内地址访问。</p>"
        "</body></html>"
    )
    assert is_blocked_page(tip_html)
    assert is_blocked_page("请使用统一身份认证登录")
    assert not is_blocked_page("学校召开运动会并圆满结束")
    extracted_title = clean_title("提示信息")
    list_title = clean_title("关于进一步规范工作的通知 2025-01-20")
    assert is_noise_title(extracted_title) and not is_noise_title(list_title)

    # 学号不当日期
    assert date_from_text("学号：20240101") is None
    assert date_from_text("发布时间：2024-01-01") is not None
    assert "<script" not in sanitize_html("<script>x</script><p>ok</p>").lower()
    assert len(SOURCES) >= 50
    assert "校园文化" in CATEGORY_ORDER

    # 正文相对 URL 必须绝对化（报告里 img/a 不丢 src/href）
    html = (
        '<html><head><title>测试新闻|大连海洋大学</title></head><body>'
        '<div class="v_news_content">'
        "<p>这里是足够长的正文内容，用于通过废文过滤规则，至少三十个字符以上。</p>"
        '<img src="../../images/pic1.png" alt="图1">'
        '<a href="../../files/a.pdf">附件下载</a>'
        "</div></body></html>"
    )
    ext = extract_article(html, "https://life.dlou.edu.cn/907/2024/01/a1b2.htm")
    assert ext["images"] and ext["images"][0]["src"].startswith("https://")
    assert "https://life.dlou.edu.cn/907/images/pic1.png" in ext["content"] or \
           "https://life.dlou.edu.cn/907/images/pic1.png" == ext["images"][0]["src"]
    sanitized = sanitize_html(ext["content"])
    assert 'src="' in sanitized and "pic1.png" in sanitized
    assert 'href="' in sanitized and "a.pdf" in sanitized
    assert ext["attachments"] and ext["attachments"][0]["url"].startswith("https://")

    # 危险协议 / 相对路径 / userinfo 绕过
    assert _safe_url("javascript:alert(1)") == ""
    assert _safe_url("/relative/path") == ""
    assert _safe_url("https://www.dlou.edu.cn/x") == "https://www.dlou.edu.cn/x"
    assert is_allowed_url("https://news.dlou.edu.cn/a")
    assert not is_allowed_url("https://evil.example.com/a")
    assert not is_allowed_url("file:///etc/passwd")
    assert not is_allowed_url("http://169.254.169.254/")
    # 白名单绕过：userinfo / 端口
    assert not is_allowed_url("http://dlou.edu.cn:80@evil.com/")
    assert not is_allowed_url("http://user:pass@evil.com/x")
    assert is_allowed_url("https://news.dlou.edu.cn:443/a")
    assert is_allowed_url("http://news.dlou.edu.cn:80/a")

    # 日期：优先「发布时间」上下文，避免把正文版本号当日期
    dt = date_from_text("版本 2024.1.15 说明 发布时间：2023-05-06 浏览次数:3")
    assert dt is not None and dt.year == 2023 and dt.month == 5 and dt.day == 6

    # 就业类路径可识别；搜索/列表页不应被当成文章
    assert is_article_link("https://dlou.jysd.com/job/123", "某单位招聘公告")
    assert not is_article_link("https://dlou.jysd.com/job/search", "就业信息")
    assert not is_article_link("https://dlou.jysd.com/campus/list.htm", "校园招聘")
    assert not is_article_link("https://www.dlou.edu.cn/89/list.htm", "信息公告")

    # sanitize：脚本与事件属性必须去掉
    dirty = '<p onclick="x()">hi</p><img src="javascript:alert(1)" onerror="y()"><script>z()</script>'
    clean = sanitize_html(dirty)
    assert "onclick" not in clean and "onerror" not in clean and "script" not in clean.lower()
    assert "hi" in clean

    art = Article(
        title="T",
        url="https://www.dlou.edu.cn/1",
        category="学校要闻",
        source="学校要闻",
        content="<p>hello world content</p>",
    )
    td = tempfile.mkdtemp()
    save_articles_csv([art], str(pathlib.Path(td) / "a.csv"))
    export_web_report([art], td)
    assert (pathlib.Path(td) / "data.js").exists()
    assert (pathlib.Path(td) / "index.html").exists()

    c = Crawler(max_workers=-5, max_articles_per_source=0)
    assert c.max_workers == 1 and c.max_articles_per_source == 1
    c2 = Crawler()
    assert 1 <= c2.max_workers <= 50

    print("== 通过 ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
