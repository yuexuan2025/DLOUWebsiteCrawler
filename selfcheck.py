"""轻量自检：python selfcheck.py"""
from __future__ import annotations

import ast
import tempfile
import pathlib
import sys

SRC_ROOT = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SRC_ROOT.parent
sys.path.insert(0, str(SRC_ROOT))


def main() -> int:
    print("== 语法 ==")
    for p in list((SRC_ROOT / "dlou_crawler").glob("*.py")) + [SRC_ROOT / "run.py", SRC_ROOT / "run_cli.py"]:
        ast.parse(p.read_text(encoding="utf-8"))
        print("  OK", p.name)

    print("== 导入 / 规则 ==")
    from dlou_crawler.html_tools import clean_title, is_noise_title, is_attachment
    from dlou_crawler.report import sanitize_html, save_articles_csv, export_web_report
    from dlou_crawler.crawler import Crawler, Article, SOURCES, CATEGORY_ORDER

    assert clean_title("[04-30]标题 - 大连海洋大学") == "标题"
    assert is_noise_title("提示信息") and is_noise_title("联系我们")
    assert not is_noise_title("学校召开运动会")
    assert is_attachment("a.zip", "公示") and not is_attachment("a/list.htm", "下载专区")
    assert "<script" not in sanitize_html("<script>x</script><p>ok</p>").lower()
    assert len(SOURCES) >= 50
    assert "校园文化" in CATEGORY_ORDER

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

    print("== 通过 ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
