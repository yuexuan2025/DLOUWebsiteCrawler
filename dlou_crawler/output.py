from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Article


def write_outputs(output_dir: Path, articles: list[Article], warnings: list[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "article_count": len(articles),
        "warnings": warnings,
        "articles": [article.to_dict() for article in articles],
    }
    (output_dir / "articles.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (output_dir / "articles.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("category", "published_at", "title", "url", "attachments", "content"),
        )
        writer.writeheader()
        for article in articles:
            writer.writerow(
                {
                    "category": article.category,
                    "published_at": article.published_at or "",
                    "title": article.title,
                    "url": article.url,
                    "attachments": "\n".join(item.url for item in article.attachments),
                    "content": article.content,
                }
            )
    lines = ["# 大连海洋大学公开信息采集报告", "", f"共采集 **{len(articles)}** 篇文章。"]
    for article in articles:
        lines.extend(
            [
                "",
                f"## {article.title}",
                "",
                f"- 栏目：{article.category}",
                f"- 日期：{article.published_at or '未识别'}",
                f"- 原文：{article.url}",
            ]
        )
        if article.attachments:
            lines.append("- 附件：")
            lines.extend(f"  - [{item.name}]({item.url})" for item in article.attachments)
        lines.extend(["", article.content[:3000]])
    if warnings:
        lines.extend(["", "## 跳过或错误", "", *[f"- {warning}" for warning in warnings]])
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
