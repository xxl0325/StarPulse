from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from typing import Protocol

from .dates import bq_table_name_for_date, validate_bq_suffix
from .storage import DailyRepoStar


class BigQueryClientLike(Protocol):
    def query(self, sql: str):
        ...


@dataclass(frozen=True, slots=True)
class DailyImportResult:
    target_date: str
    table_name: str
    sql: str
    rows: list[DailyRepoStar]


def build_daily_watch_event_sql(*, target_date: str, dataset: str, limit: int) -> str:
    if limit <= 0:
        raise ValueError("limit must be positive")
    table_name = bq_table_name_for_date(target_date, dataset)
    return f"""
SELECT
  repo.name AS repo_name,
  COUNT(*) AS star_delta
FROM
  `{table_name}`
WHERE
  type = 'WatchEvent'
GROUP BY
  repo_name
ORDER BY
  star_delta DESC, repo_name ASC
LIMIT {int(limit)}
""".strip()


def create_bigquery_client(project: str, credentials_path=None):
    try:
        from google.cloud import bigquery
    except ImportError as exc:  # pragma: no cover - dependency missing only in broken envs
        raise RuntimeError("google-cloud-bigquery is required for BigQuery import") from exc
    _ = credentials_path
    return bigquery.Client(project=project)


def query_daily_watch_events(
    client: BigQueryClientLike,
    *,
    target_date: str,
    dataset: str = "githubarchive.day",
    limit: int = 500,
) -> DailyImportResult:
    table_name = bq_table_name_for_date(target_date, dataset)
    sql = build_daily_watch_event_sql(target_date=target_date, dataset=dataset, limit=limit)
    job = client.query(sql)
    result = job.result()
    rows: list[DailyRepoStar] = []
    for index, row in enumerate(result, start=1):
        if isinstance(row, Mapping):
            row_dict = dict(row)
        else:
            row_dict = {key: row[key] for key in ("repo_name", "star_delta")}
        repo_name = row_dict["repo_name"]
        star_delta = int(row_dict["star_delta"])
        rows.append(
            DailyRepoStar(
                date=target_date,
                repo_name=repo_name,
                star_delta=star_delta,
                rank=index,
                html_url=f"https://github.com/{repo_name}",
            )
        )
    return DailyImportResult(target_date=target_date, table_name=table_name, sql=sql, rows=rows)
