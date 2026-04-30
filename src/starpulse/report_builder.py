from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .storage import RepoMetadata


SYSTEM_PROMPT = (
    "你是开源项目情报分析员。只能基于输入 JSON 中的事实写日报。"
    "如果事实不足，明确写“信息不足”，不要猜测。"
    "不要编造项目用途、作者背景、商业进展、融资信息。"
    "输出简短中文 Markdown。"
)


def _parse_topics(topics_json: str | None) -> list[str]:
    if not topics_json:
        return []
    try:
        topics = json.loads(topics_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(topics, list):
        return []
    return [str(topic) for topic in topics]


def _shorten(text: str | None, max_length: int = 80) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "…"


def _normalize_metadata(metadata: RepoMetadata | None) -> dict[str, Any]:
    if metadata is None:
        return {
            "description": None,
            "language": None,
            "topics": [],
            "license": None,
            "stars": None,
            "forks": None,
            "readme_available": False,
            "readme_excerpt": None,
        }
    return {
        "description": metadata.description,
        "language": metadata.language,
        "topics": _parse_topics(metadata.topics_json),
        "license": metadata.license,
        "stars": metadata.stars,
        "forks": metadata.forks,
        "readme_available": bool(metadata.readme_excerpt),
        "readme_excerpt": metadata.readme_excerpt,
    }


def _merge_row_with_metadata(row: Mapping[str, Any], metadata: RepoMetadata | None) -> dict[str, Any]:
    merged = dict(row)
    merged.update(_normalize_metadata(metadata))
    return merged


def build_daily_report_payload(
    *,
    date: str,
    top20_rows: Sequence[Mapping[str, Any]],
    burst_rows: Sequence[Mapping[str, Any]],
    metadata_by_repo: Mapping[str, RepoMetadata],
) -> dict[str, Any]:
    top20 = [
        _merge_row_with_metadata(row, metadata_by_repo.get(str(row["repo_name"])))
        for row in top20_rows
    ]
    burst_top5 = [
        _merge_row_with_metadata(row, metadata_by_repo.get(str(row["repo_name"])))
        for row in burst_rows
    ]
    overview = {
        "date": date,
        "top20_total_star_delta": sum(int(row["star_delta"]) for row in top20_rows),
        "top20_count": len(top20),
        "burst_count": len(burst_top5),
        "top_project": top20[0]["repo_name"] if top20 else None,
        "top_project_star_delta": int(top20[0]["star_delta"]) if top20 else None,
    }
    return {
        "date": date,
        "overview": overview,
        "top20": top20,
        "burst_top5": burst_top5,
    }


def render_fallback_report(payload: Mapping[str, Any]) -> str:
    overview = payload["overview"]
    top20 = list(payload["top20"])
    burst_top5 = list(payload["burst_top5"])

    lines = [
        f"# StarPulse Daily Report - {payload['date']}",
        "",
        "## 今日概览",
        f"- Top20 总新增 Star: {overview['top20_total_star_delta']}",
        f"- 最高增长项目: {overview['top_project'] or '信息不足'}",
        f"- 突然爆发项目数: {overview['burst_count']}",
        "",
        "## 今日重点",
    ]
    focus_rows = top20[:5]
    if not focus_rows:
        lines.append("- 信息不足")
    for row in focus_rows:
        description = _shorten(row.get("description"), 40) or "信息不足"
        language = row.get("language") or "信息不足"
        lines.append(
            f"- {row['repo_name']}：{row['star_delta']} Star，{language}，{description}"
        )

    lines.extend(
        [
            "",
            "## Top20",
            "|Rank|Repo|Stars|Language|Summary|",
            "|---|---|---:|---|---|",
        ]
    )
    for row in top20:
        summary = _shorten(row.get("description"), 40) or _shorten(row.get("readme_excerpt"), 40) or "信息不足"
        lines.append(
            f"|{row['rank']}|{row['repo_name']}|{row['star_delta']}|{row.get('language') or '信息不足'}|{summary}|"
        )

    lines.extend(["", "## 突然爆发 Top5", "|Repo|Burst Score|Stars|", "|---|---:|---:|"])
    if not burst_top5:
        lines.append("|信息不足|0|0|")
    for row in burst_top5[:5]:
        lines.append(
            f"|{row['repo_name']}|{row.get('burst_score', 0)}|{row.get('yesterday_stars', row.get('star_delta', 0))}|"
        )

    return "\n".join(lines).strip() + "\n"


def render_provider_prompt_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "date": payload["date"],
        "overview": payload["overview"],
        "top20": payload["top20"],
        "burst_top5": payload["burst_top5"],
    }


def serialize_report_payload(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
