from __future__ import annotations

import sqlite3

from starpulse.rankings import (
    fetch_burst_ranking,
    fetch_daily_ranking,
    fetch_trend_ranking,
    fetch_weekly_ranking,
)
from starpulse.storage import (
    DailyReport,
    DailyRepoStar,
    RepoMetadata,
    init_db,
    load_daily_report,
    mark_daily_report_sent,
    save_daily_report,
    upsert_daily_repo_stars,
    upsert_repo_metadata,
)


def seed_rows():
    return [
        DailyRepoStar("2026-04-27", "a/repo", 10, 1, "https://github.com/a/repo"),
        DailyRepoStar("2026-04-27", "b/repo", 6, 2, "https://github.com/b/repo"),
        DailyRepoStar("2026-04-28", "a/repo", 20, 1, "https://github.com/a/repo"),
        DailyRepoStar("2026-04-28", "c/repo", 12, 2, "https://github.com/c/repo"),
        DailyRepoStar("2026-04-29", "a/repo", 40, 1, "https://github.com/a/repo"),
        DailyRepoStar("2026-04-29", "d/repo", 25, 2, "https://github.com/d/repo"),
        DailyRepoStar("2026-04-30", "a/repo", 8, 1, "https://github.com/a/repo"),
        DailyRepoStar("2026-04-30", "d/repo", 30, 2, "https://github.com/d/repo"),
    ]


def test_init_db_creates_schema(tmp_path):
    db_path = tmp_path / "starpulse.sqlite3"
    init_db(db_path)

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"daily_repo_stars", "repo_metadata", "daily_reports"}.issubset(tables)
    conn.close()


def test_daily_upsert_is_idempotent(tmp_path):
    db_path = tmp_path / "starpulse.sqlite3"
    init_db(db_path)
    rows = [DailyRepoStar("2026-04-29", "a/repo", 40, 1, "https://github.com/a/repo")]

    assert upsert_daily_repo_stars(db_path, rows) == 1
    assert upsert_daily_repo_stars(db_path, rows) == 1

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM daily_repo_stars").fetchone()[0]
    conn.close()
    assert count == 1


def test_ranking_queries(tmp_path):
    db_path = tmp_path / "starpulse.sqlite3"
    init_db(db_path)
    upsert_daily_repo_stars(db_path, seed_rows())

    daily = fetch_daily_ranking(db_path, "2026-04-29", limit=10)
    assert [row["repo_name"] for row in daily] == ["a/repo", "d/repo"]

    weekly = fetch_weekly_ranking(db_path, "2026-04-27", "2026-04-30", limit=10)
    assert weekly[0]["repo_name"] == "a/repo"
    assert weekly[0]["stars_7d"] == 78

    trend = fetch_trend_ranking(
        db_path,
        recent_start="2026-04-29",
        recent_end="2026-04-30",
        previous_start="2026-04-27",
        previous_end="2026-04-28",
        min_recent_stars=1,
        limit=10,
    )
    assert trend[0]["repo_name"] == "d/repo"
    assert trend[0]["trend_score"] == 55

    burst = fetch_burst_ranking(
        db_path,
        yesterday="2026-04-30",
        baseline_start="2026-04-27",
        baseline_end="2026-04-29",
        min_yesterday_stars=5,
        min_burst_ratio=1.0,
        limit=10,
    )
    assert burst[0]["repo_name"] == "d/repo"


def test_repo_metadata_and_reports(tmp_path):
    db_path = tmp_path / "starpulse.sqlite3"
    init_db(db_path)

    metadata_rows = [
        RepoMetadata(
            repo_name="a/repo",
            html_url="https://github.com/a/repo",
            description="demo",
            language="Python",
            topics_json='["ai"]',
            stars=100,
            forks=10,
            license="MIT",
            readme_excerpt="hello",
        )
    ]
    assert upsert_repo_metadata(db_path, metadata_rows) == 1

    report = DailyReport(
        date="2026-04-29",
        report_markdown="# report",
        report_json='{"ok": true}',
        llm_provider="openai-compatible",
        llm_model="gpt-4.1-mini",
    )
    save_daily_report(db_path, report)
    saved = load_daily_report(db_path, "2026-04-29")
    assert saved is not None
    assert saved.report_markdown == "# report"
    assert saved.sent_to_dingtalk == 0

    mark_daily_report_sent(db_path, "2026-04-29")
    marked = load_daily_report(db_path, "2026-04-29")
    assert marked is not None
    assert marked.sent_to_dingtalk == 1
