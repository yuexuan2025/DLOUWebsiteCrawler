"""命令行采集入口：python run_cli.py [--limit N] [--out DIR]"""
from __future__ import annotations

import argparse
import os
import sys

from dlou_crawler.crawler import Crawler
from dlou_crawler.report import save_articles_json, save_articles_csv, export_web_report


def main() -> int:
    parser = argparse.ArgumentParser(description="大连海洋大学官网采集器（命令行）")
    parser.add_argument("--limit", type=int, default=15, help="每栏目最大文章数，默认 15")
    parser.add_argument("--workers", type=int, default=20, help="并发线程数，默认 20")
    parser.add_argument("--out", type=str, default="output", help="输出目录，默认 源代码/output（相对当前工作目录）")
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 50:
        parser.error("--limit 必须在 1–50 之间")
    if args.workers < 1 or args.workers > 50:
        parser.error("--workers 必须在 1–50 之间")

    out_dir = args.out
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError as e:
        print(f"无法创建输出目录 {out_dir}: {e}", file=sys.stderr)
        return 1

    def log(msg: str) -> None:
        print(msg, flush=True)

    crawler = Crawler(
        max_workers=args.workers,
        max_articles_per_source=args.limit,
        log_callback=log,
    )
    articles = crawler.crawl()
    if not articles:
        print("未采集到任何文章", file=sys.stderr)
        return 1

    json_path = os.path.join(out_dir, "articles.json")
    save_articles_json(articles, json_path)
    print(f"JSON 已写入：{json_path}")

    csv_path = os.path.join(out_dir, "articles.csv")
    save_articles_csv(articles, csv_path)
    print(f"CSV  已写入：{csv_path}")

    # 唯一报告入口：output/index.html（含 data.js，file:// 可直接打开）
    report_path = export_web_report(articles, out_dir, getattr(crawler, "source_stats", None))
    print(f"报告已写入：{report_path}")

    print(f"共 {len(articles)} 篇文章")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
