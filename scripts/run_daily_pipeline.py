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

from starpulse.config import load_settings  # noqa: E402
from starpulse.dates import DateFormatError, parse_ymd  # noqa: E402
from starpulse.pipeline import run_daily_pipeline  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="StarPulse daily pipeline")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD")
    parser.add_argument("--db-path", default=None, help="SQLite database path")
    parser.add_argument("--limit", type=int, default=None, help="BigQuery Top N limit")
    parser.add_argument("--report-top-n", type=int, default=None, help="Report Top N rows")
    parser.add_argument("--skip-llm", action="store_true", help="Skip report generation")
    parser.add_argument("--skip-dingtalk", action="store_true", help="Skip DingTalk delivery")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.date:
        try:
            parse_ymd(args.date)
        except DateFormatError as exc:
            raise SystemExit(str(exc)) from exc
    settings = load_settings()
    result = run_daily_pipeline(
        settings,
        target_date=args.date,
        db_path=args.db_path,
        import_limit=args.limit,
        report_top_n=args.report_top_n,
        skip_llm=args.skip_llm,
        skip_dingtalk=args.skip_dingtalk,
    )
    print(
        f"date={result.date} imported_rows={result.imported_rows} "
        f"metadata_rows={result.metadata_rows} report_sent={result.report_sent} used_llm={result.used_llm}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
