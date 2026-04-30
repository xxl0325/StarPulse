from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .storage import connect


def _rows_as_dicts(cursor) -> list[dict[str, Any]]:
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def fetch_daily_ranking(db_path: str | Path, target_date: str, limit: int = 20) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT rank, repo_name, star_delta, html_url
            FROM daily_repo_stars
            WHERE date = ?
            ORDER BY rank ASC
            LIMIT ?
            """,
            (target_date, limit),
        )
        return _rows_as_dicts(cursor)


def fetch_weekly_ranking(db_path: str | Path, start_date: str, end_date: str, limit: int = 20) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            SELECT
              repo_name,
              SUM(star_delta) AS stars_7d,
              COUNT(*) AS active_days,
              MAX(html_url) AS html_url
            FROM daily_repo_stars
            WHERE date BETWEEN ? AND ?
            GROUP BY repo_name
            ORDER BY stars_7d DESC, repo_name ASC
            LIMIT ?
            """,
            (start_date, end_date, limit),
        )
        return _rows_as_dicts(cursor)


def fetch_trend_ranking(
    db_path: str | Path,
    recent_start: str,
    recent_end: str,
    previous_start: str,
    previous_end: str,
    min_recent_stars: int = 1,
    limit: int = 20,
) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            WITH recent AS (
              SELECT repo_name, SUM(star_delta) AS recent_3d_stars, MAX(html_url) AS html_url
              FROM daily_repo_stars
              WHERE date BETWEEN ? AND ?
              GROUP BY repo_name
            ),
            previous AS (
              SELECT repo_name, SUM(star_delta) AS previous_3d_stars
              FROM daily_repo_stars
              WHERE date BETWEEN ? AND ?
              GROUP BY repo_name
            )
            SELECT
              recent.repo_name,
              recent.recent_3d_stars,
              COALESCE(previous.previous_3d_stars, 0) AS previous_3d_stars,
              recent.recent_3d_stars - COALESCE(previous.previous_3d_stars, 0) AS trend_score,
              1.0 * recent.recent_3d_stars / MAX(COALESCE(previous.previous_3d_stars, 0), 1) AS trend_ratio,
              recent.html_url AS html_url
            FROM recent
            LEFT JOIN previous ON previous.repo_name = recent.repo_name
            WHERE recent.recent_3d_stars >= ?
            ORDER BY (recent.recent_3d_stars - COALESCE(previous.previous_3d_stars, 0)) DESC, recent.repo_name ASC
            LIMIT ?
            """,
            (recent_start, recent_end, previous_start, previous_end, min_recent_stars, limit),
        )
        return _rows_as_dicts(cursor)


def fetch_burst_ranking(
    db_path: str | Path,
    yesterday: str,
    baseline_start: str,
    baseline_end: str,
    min_yesterday_stars: int = 20,
    min_burst_ratio: float = 2.0,
    limit: int = 20,
) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            WITH yesterday AS (
              SELECT repo_name, star_delta AS yesterday_stars, html_url
              FROM daily_repo_stars
              WHERE date = ?
            ),
            baseline AS (
              SELECT repo_name, AVG(star_delta) AS avg_previous_7d_stars
              FROM daily_repo_stars
              WHERE date BETWEEN ? AND ?
              GROUP BY repo_name
            )
            SELECT
              yesterday.repo_name,
              yesterday.yesterday_stars,
              COALESCE(baseline.avg_previous_7d_stars, 0) AS avg_previous_7d_stars,
              yesterday.yesterday_stars - COALESCE(baseline.avg_previous_7d_stars, 0) AS burst_score,
              1.0 * yesterday.yesterday_stars / MAX(COALESCE(baseline.avg_previous_7d_stars, 0), 1) AS burst_ratio,
              yesterday.html_url
            FROM yesterday
            LEFT JOIN baseline ON baseline.repo_name = yesterday.repo_name
            WHERE yesterday.yesterday_stars >= ?
              AND 1.0 * yesterday.yesterday_stars / MAX(COALESCE(baseline.avg_previous_7d_stars, 0), 1) >= ?
            ORDER BY burst_score DESC, yesterday.repo_name ASC
            LIMIT ?
            """,
            (yesterday, baseline_start, baseline_end, min_yesterday_stars, min_burst_ratio, limit),
        )
        return _rows_as_dicts(cursor)
