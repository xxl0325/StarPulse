from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=False)

from starpulse.bigquery_daily import create_bigquery_client, query_daily_watch_events  # noqa: E402
from starpulse.config import load_settings  # noqa: E402
from starpulse.dates import yesterday_in_timezone  # noqa: E402
from starpulse.storage import init_db, upsert_daily_repo_stars  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a daily GH Archive Top500 snapshot")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD")
    parser.add_argument("--db-path", default=None, help="SQLite database path")
    parser.add_argument("--limit", type=int, default=None, help="BigQuery Top N limit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    target_date = args.date or yesterday_in_timezone(settings.timezone).isoformat()
    db_path = args.db_path or settings.sqlite_path
    init_db(db_path)
    settings.require_bigquery()
    client = create_bigquery_client(
        settings.gcp_project or "",
        settings.google_application_credentials,
    )
    result = query_daily_watch_events(
        client,
        target_date=target_date,
        dataset=settings.github_daily_dataset,
        limit=args.limit or settings.top_n,
    )
    imported = upsert_daily_repo_stars(db_path, result.rows)
    print(f"date={target_date} imported_rows={imported}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
