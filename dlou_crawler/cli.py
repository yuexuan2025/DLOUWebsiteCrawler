from __future__ import annotations

import argparse
from pathlib import Path

from .client import PoliteClient
from .crawler import DlouCrawler
from .output import write_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="采集大连海洋大学官网公开的新闻、通知和附件链接。"
    )
    parser.add_argument("--pages", type=int, default=1, help="每个栏目最多采集的列表页数（默认 1）")
    parser.add_argument("--max-articles", type=int, default=20, help="最多采集文章数（默认 20）")
    parser.add_argument("--delay", type=float, default=1.0, help="两次请求的最短间隔（默认 1 秒）")
    parser.add_argument("--output", type=Path, default=Path("output"), help="结果保存目录")
    parser.add_argument("--download-files", action="store_true", help="下载文章中的公开附件")
    parser.add_argument(
        "--user-agent",
        default="DlouStudentCrawler/1.0 (personal educational use)",
        help="请求标识；请勿伪装成浏览器绕过限制",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.pages < 1 or args.max_articles < 1:
        raise SystemExit("--pages 和 --max-articles 必须大于 0。")
    if args.delay < 1:
        raise SystemExit("为保护学校网站，--delay 不能小于 1 秒。")
    client = PoliteClient(args.user_agent, args.delay)
    crawler = DlouCrawler(
        client=client,
        pages_per_source=args.pages,
        max_articles=args.max_articles,
        download_files=args.download_files,
        output_dir=args.output,
    )
    articles = crawler.crawl()
    write_outputs(args.output, articles, crawler.warnings)
    print(f"完成：采集 {len(articles)} 篇文章，结果已保存到 {args.output.resolve()}")
    if crawler.warnings:
        print(f"提示：有 {len(crawler.warnings)} 条跳过或错误信息，详情见 report.md。")
