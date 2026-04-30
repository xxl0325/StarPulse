from __future__ import annotations

from starpulse.bigquery_daily import build_daily_watch_event_sql, query_daily_watch_events


class FakeJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeClient:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None

    def query(self, sql):
        self.sql = sql
        return FakeJob(self.rows)


def test_build_daily_watch_event_sql_uses_single_table():
    sql = build_daily_watch_event_sql(
        target_date="2026-04-29",
        dataset="githubarchive.day",
        limit=500,
    )
    assert "`githubarchive.day.20260429`" in sql
    assert "type = 'WatchEvent'" in sql
    assert "LIMIT 500" in sql


def test_query_daily_watch_events_enumerates_rank():
    client = FakeClient(
        [
            {"repo_name": "a/repo", "star_delta": 12},
            {"repo_name": "b/repo", "star_delta": 7},
        ]
    )
    result = query_daily_watch_events(client, target_date="2026-04-29", limit=500)

    assert result.table_name == "githubarchive.day.20260429"
    assert [row.rank for row in result.rows] == [1, 2]
    assert [row.repo_name for row in result.rows] == ["a/repo", "b/repo"]
    assert "WatchEvent" in client.sql

