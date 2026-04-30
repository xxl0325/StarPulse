from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import json
import sqlite3
from pathlib import Path
from typing import Iterator, Mapping, Sequence


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS daily_repo_stars (
  date TEXT NOT NULL,
  repo_name TEXT NOT NULL,
  star_delta INTEGER NOT NULL,
  rank INTEGER NOT NULL,
  html_url TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (date, repo_name)
);

CREATE INDEX IF NOT EXISTS idx_daily_repo_stars_date_rank
  ON daily_repo_stars (date, rank);

CREATE INDEX IF NOT EXISTS idx_daily_repo_stars_repo_date
  ON daily_repo_stars (repo_name, date);

CREATE TABLE IF NOT EXISTS repo_metadata (
  repo_name TEXT PRIMARY KEY,
  html_url TEXT NOT NULL,
  description TEXT,
  language TEXT,
  topics_json TEXT,
  stars INTEGER,
  forks INTEGER,
  license TEXT,
  readme_excerpt TEXT,
  fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS daily_reports (
  date TEXT PRIMARY KEY,
  report_markdown TEXT NOT NULL,
  report_json TEXT,
  llm_provider TEXT NOT NULL,
  llm_model TEXT NOT NULL,
  sent_to_dingtalk INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(frozen=True, slots=True)
class DailyRepoStar:
    date: str
    repo_name: str
    star_delta: int
    rank: int
    html_url: str


@dataclass(frozen=True, slots=True)
class RepoMetadata:
    repo_name: str
    html_url: str
    description: str | None = None
    language: str | None = None
    topics_json: str | None = None
    stars: int | None = None
    forks: int | None = None
    license: str | None = None
    readme_excerpt: str | None = None

    @classmethod
    def from_topics(cls, topics: Sequence[str], **kwargs):
        return cls(topics_json=json.dumps(list(topics), ensure_ascii=False), **kwargs)


@dataclass(frozen=True, slots=True)
class DailyReport:
    date: str
    report_markdown: str
    report_json: str | None
    llm_provider: str
    llm_model: str
    sent_to_dingtalk: int = 0


def _connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    conn = _connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def upsert_daily_repo_stars(db_path: str | Path, rows: Sequence[DailyRepoStar]) -> int:
    if not rows:
        return 0
    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO daily_repo_stars (
              date, repo_name, star_delta, rank, html_url, created_at
            ) VALUES (
              :date, :repo_name, :star_delta, :rank, :html_url, CURRENT_TIMESTAMP
            )
            ON CONFLICT(date, repo_name) DO UPDATE SET
              star_delta = excluded.star_delta,
              rank = excluded.rank,
              html_url = excluded.html_url,
              created_at = CURRENT_TIMESTAMP
            """,
            [asdict(row) for row in rows],
        )
        conn.commit()
    return len(rows)


def upsert_repo_metadata(db_path: str | Path, rows: Sequence[RepoMetadata]) -> int:
    if not rows:
        return 0
    with connect(db_path) as conn:
        conn.executemany(
            """
            INSERT INTO repo_metadata (
              repo_name, html_url, description, language, topics_json,
              stars, forks, license, readme_excerpt, fetched_at
            ) VALUES (
              :repo_name, :html_url, :description, :language, :topics_json,
              :stars, :forks, :license, :readme_excerpt, CURRENT_TIMESTAMP
            )
            ON CONFLICT(repo_name) DO UPDATE SET
              html_url = excluded.html_url,
              description = excluded.description,
              language = excluded.language,
              topics_json = excluded.topics_json,
              stars = excluded.stars,
              forks = excluded.forks,
              license = excluded.license,
              readme_excerpt = excluded.readme_excerpt,
              fetched_at = CURRENT_TIMESTAMP
            """,
            [asdict(row) for row in rows],
        )
        conn.commit()
    return len(rows)


def save_daily_report(db_path: str | Path, report: DailyReport) -> None:
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO daily_reports (
              date, report_markdown, report_json, llm_provider, llm_model, sent_to_dingtalk, created_at
            ) VALUES (
              :date, :report_markdown, :report_json, :llm_provider, :llm_model, :sent_to_dingtalk, CURRENT_TIMESTAMP
            )
            ON CONFLICT(date) DO UPDATE SET
              report_markdown = excluded.report_markdown,
              report_json = excluded.report_json,
              llm_provider = excluded.llm_provider,
              llm_model = excluded.llm_model,
              sent_to_dingtalk = excluded.sent_to_dingtalk,
              created_at = CURRENT_TIMESTAMP
            """,
            asdict(report),
        )
        conn.commit()


def mark_daily_report_sent(db_path: str | Path, date: str) -> None:
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE daily_reports SET sent_to_dingtalk = 1, created_at = CURRENT_TIMESTAMP WHERE date = ?",
            (date,),
        )
        conn.commit()


def load_daily_report(db_path: str | Path, date: str) -> DailyReport | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT date, report_markdown, report_json, llm_provider, llm_model, sent_to_dingtalk
            FROM daily_reports
            WHERE date = ?
            """,
            (date,),
        ).fetchone()
    if row is None:
        return None
    return DailyReport(
        date=row["date"],
        report_markdown=row["report_markdown"],
        report_json=row["report_json"],
        llm_provider=row["llm_provider"],
        llm_model=row["llm_model"],
        sent_to_dingtalk=int(row["sent_to_dingtalk"]),
    )


def load_repo_metadata(db_path: str | Path, repo_names: Sequence[str]) -> dict[str, RepoMetadata]:
    if not repo_names:
        return {}
    placeholders = ",".join("?" for _ in repo_names)
    query = f"""
        SELECT
          repo_name, html_url, description, language, topics_json,
          stars, forks, license, readme_excerpt
        FROM repo_metadata
        WHERE repo_name IN ({placeholders})
    """
    with connect(db_path) as conn:
        rows = conn.execute(query, list(repo_names)).fetchall()
    result: dict[str, RepoMetadata] = {}
    for row in rows:
        result[row["repo_name"]] = RepoMetadata(
            repo_name=row["repo_name"],
            html_url=row["html_url"],
            description=row["description"],
            language=row["language"],
            topics_json=row["topics_json"],
            stars=row["stars"],
            forks=row["forks"],
            license=row["license"],
            readme_excerpt=row["readme_excerpt"],
        )
    return result
