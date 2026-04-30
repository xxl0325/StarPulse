from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Sequence

from .bigquery_daily import DailyImportResult, create_bigquery_client, query_daily_watch_events
from .config import ConfigError, Settings
from .dates import normalize_date, yesterday_in_timezone
from .dingtalk import DingTalkClient
from .github_metadata import GitHubAPIError, fetch_repo_metadata
from .llm_provider import LLMProviderError, OpenAICompatibleProvider
from .rankings import fetch_burst_ranking, fetch_daily_ranking
from .report_builder import (
    SYSTEM_PROMPT,
    build_daily_report_payload,
    render_fallback_report,
    render_provider_prompt_payload,
    serialize_report_payload,
)
from .storage import (
    DailyReport,
    RepoMetadata,
    init_db,
    load_daily_report,
    load_repo_metadata,
    mark_daily_report_sent,
    save_daily_report,
    upsert_daily_repo_stars,
    upsert_repo_metadata,
)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    date: str
    imported_rows: int
    metadata_rows: int
    report_sent: bool
    used_llm: bool


def _date_str(value: str | date) -> str:
    return normalize_date(value).isoformat()


def _window_days(target_date: date, days_back: int) -> tuple[str, str]:
    start = target_date - timedelta(days=days_back)
    end = target_date - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _build_daily_rows(db_path: str | Path, target_date: str) -> list[dict]:
    return fetch_daily_ranking(db_path, target_date, limit=20)


def _build_burst_rows(db_path: str | Path, target_date: str) -> list[dict]:
    dt = normalize_date(target_date)
    baseline_start, baseline_end = _window_days(dt, 7)
    return fetch_burst_ranking(
        db_path,
        yesterday=target_date,
        baseline_start=baseline_start,
        baseline_end=baseline_end,
        min_yesterday_stars=20,
        min_burst_ratio=2.0,
        limit=5,
    )


def _refresh_metadata_for_repos(
    *,
    db_path: str | Path,
    repo_names: Sequence[str],
    settings: Settings,
    fetcher: Callable[..., RepoMetadata],
) -> int:
    unique_names = [name for name in dict.fromkeys(repo_names) if name]
    existing = load_repo_metadata(db_path, unique_names)
    missing = [name for name in unique_names if name not in existing]
    fetched: list[RepoMetadata] = []
    for repo_name in missing:
        try:
            fetched.append(
                fetcher(
                    repo_name,
                    token=settings.github_token,
                    base_url=settings.github_api_base_url,
                    readme_excerpt_chars=settings.readme_excerpt_chars,
                )
            )
        except GitHubAPIError:
            continue
    if fetched:
        upsert_repo_metadata(db_path, fetched)
    return len(fetched)


def _build_llm_provider(settings: Settings) -> OpenAICompatibleProvider:
    settings.require_llm()
    return OpenAICompatibleProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key or "",
        model=settings.llm_model or "",
    )


def _build_dingtalk_client(settings: Settings) -> DingTalkClient:
    settings.require_dingtalk()
    return DingTalkClient(
        webhook_url=settings.dingtalk_webhook_url or "",
        keyword=settings.dingtalk_keyword,
        secret=settings.dingtalk_secret,
    )


def run_daily_pipeline(
    settings: Settings,
    *,
    target_date: str | date | None = None,
    db_path: str | Path | None = None,
    import_limit: int | None = None,
    report_top_n: int | None = None,
    skip_llm: bool = False,
    skip_dingtalk: bool = False,
    bigquery_client=None,
    metadata_fetcher: Callable[..., RepoMetadata] = fetch_repo_metadata,
    llm_provider=None,
    dingtalk_client=None,
) -> PipelineResult:
    target = normalize_date(target_date or yesterday_in_timezone(settings.timezone))
    target_str = target.isoformat()
    db_file = Path(db_path or settings.sqlite_path)
    init_db(db_file)

    if bigquery_client is None:
        settings.require_bigquery()
        bigquery_client = create_bigquery_client(
            settings.gcp_project or "",
            settings.google_application_credentials,
        )

    import_result: DailyImportResult = query_daily_watch_events(
        bigquery_client,
        target_date=target_str,
        dataset=settings.github_daily_dataset,
        limit=import_limit or settings.top_n,
    )
    imported_rows = upsert_daily_repo_stars(db_file, import_result.rows)

    report_limit = report_top_n or settings.report_top_n
    daily_rows = fetch_daily_ranking(db_file, target_str, limit=report_limit)
    burst_rows = _build_burst_rows(db_file, target_str)
    metadata_repo_names = [row["repo_name"] for row in daily_rows] + [row["repo_name"] for row in burst_rows]
    metadata_rows = _refresh_metadata_for_repos(
        db_path=db_file,
        repo_names=metadata_repo_names,
        settings=settings,
        fetcher=metadata_fetcher,
    )
    metadata_map = load_repo_metadata(db_file, metadata_repo_names)
    report_payload = build_daily_report_payload(
        date=target_str,
        top20_rows=daily_rows,
        burst_rows=burst_rows,
        metadata_by_repo=metadata_map,
    )

    if skip_llm:
        report_markdown = render_fallback_report(report_payload)
        llm_provider_name = "fallback"
        llm_model_name = "fallback"
        used_llm = False
    else:
        provider = llm_provider or _build_llm_provider(settings)
        report_markdown = provider.generate(
            system_prompt=SYSTEM_PROMPT,
            payload=render_provider_prompt_payload(report_payload),
        )
        llm_provider_name = settings.llm_provider
        llm_model_name = settings.llm_model or "unknown"
        used_llm = True

    save_daily_report(
        db_file,
        DailyReport(
            date=target_str,
            report_markdown=report_markdown,
            report_json=serialize_report_payload(report_payload),
            llm_provider=llm_provider_name,
            llm_model=llm_model_name,
            sent_to_dingtalk=0,
        ),
    )

    report_sent = False
    if not skip_dingtalk:
        client = dingtalk_client or _build_dingtalk_client(settings)
        client.send_markdown(title=f"StarPulse Daily {target_str}", markdown=report_markdown)
        mark_daily_report_sent(db_file, target_str)
        report_sent = True

    return PipelineResult(
        date=target_str,
        imported_rows=imported_rows,
        metadata_rows=metadata_rows,
        report_sent=report_sent,
        used_llm=used_llm,
    )


def resend_daily_report(
    settings: Settings,
    *,
    target_date: str | date,
    db_path: str | Path | None = None,
    dingtalk_client=None,
) -> bool:
    target_str = _date_str(target_date)
    db_file = Path(db_path or settings.sqlite_path)
    report = load_daily_report(db_file, target_str)
    if report is None:
        raise ConfigError(f"no saved report for {target_str}")
    client = dingtalk_client or _build_dingtalk_client(settings)
    client.send_markdown(title=f"StarPulse Daily {target_str}", markdown=report.report_markdown)
    mark_daily_report_sent(db_file, target_str)
    return True
