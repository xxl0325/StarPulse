from __future__ import annotations

import sqlite3

from starpulse.config import load_settings
from starpulse.pipeline import resend_daily_report, run_daily_pipeline
from starpulse.storage import DailyRepoStar, RepoMetadata, init_db, load_daily_report


class FakeJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeBigQueryClient:
    def __init__(self, rows):
        self.rows = rows

    def query(self, sql):
        self.sql = sql
        return FakeJob(self.rows)


class FakeLLMProvider:
    def __init__(self):
        self.calls = []

    def generate(self, *, system_prompt, payload):
        self.calls.append((system_prompt, payload))
        return "# fake report\n"


class FakeDingTalkClient:
    def __init__(self):
        self.calls = []

    def send_markdown(self, title, markdown):
        self.calls.append((title, markdown))
        return {"errcode": 0, "errmsg": "ok"}


def fake_metadata_fetcher(repo_name, **kwargs):
    return RepoMetadata(
        repo_name=repo_name,
        html_url=f"https://github.com/{repo_name}",
        description=f"{repo_name} description",
        language="Python",
        topics_json='["demo"]',
        stars=100,
        forks=10,
        license="MIT",
        readme_excerpt=f"{repo_name} readme",
    )


def test_run_daily_pipeline_happy_path(tmp_path):
    db_path = tmp_path / "starpulse.sqlite3"
    settings = load_settings(
        {
            "SQLITE_PATH": str(db_path),
            "TIMEZONE": "UTC",
            "GITHUB_DAILY_DATASET": "githubarchive.day",
        }
    )
    init_db(db_path)
    bigquery_client = FakeBigQueryClient(
        [
            {"repo_name": "a/repo", "star_delta": 12},
            {"repo_name": "b/repo", "star_delta": 7},
        ]
    )
    llm = FakeLLMProvider()
    dingtalk = FakeDingTalkClient()

    result = run_daily_pipeline(
        settings,
        target_date="2026-04-29",
        db_path=db_path,
        bigquery_client=bigquery_client,
        metadata_fetcher=fake_metadata_fetcher,
        llm_provider=llm,
        dingtalk_client=dingtalk,
        skip_llm=False,
        skip_dingtalk=False,
        import_limit=500,
        report_top_n=20,
    )

    assert result.imported_rows == 2
    assert result.metadata_rows == 2
    assert result.report_sent is True
    assert result.used_llm is True
    assert llm.calls
    assert dingtalk.calls

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM daily_repo_stars").fetchone()[0]
    report_row = conn.execute("SELECT sent_to_dingtalk FROM daily_reports WHERE date = ?", ("2026-04-29",)).fetchone()
    conn.close()
    assert count == 2
    assert report_row[0] == 1


def test_resend_daily_report_uses_saved_content(tmp_path):
    db_path = tmp_path / "starpulse.sqlite3"
    settings = load_settings({"SQLITE_PATH": str(db_path), "TIMEZONE": "UTC"})
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO daily_reports (
          date, report_markdown, report_json, llm_provider, llm_model, sent_to_dingtalk
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("2026-04-29", "# saved report", "{}", "fallback", "fallback", 0),
    )
    conn.commit()
    conn.close()

    dingtalk = FakeDingTalkClient()
    assert resend_daily_report(settings, target_date="2026-04-29", db_path=db_path, dingtalk_client=dingtalk)
    assert dingtalk.calls[0][1] == "# saved report"
    saved = load_daily_report(db_path, "2026-04-29")
    assert saved is not None
    assert saved.sent_to_dingtalk == 1

