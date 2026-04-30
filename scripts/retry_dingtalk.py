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
from starpulse.pipeline import resend_daily_report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resend a stored StarPulse report to DingTalk")
    parser.add_argument("--date", required=True, help="Target date in YYYY-MM-DD")
    parser.add_argument("--db-path", default=None, help="SQLite database path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    resend_daily_report(settings, target_date=args.date, db_path=args.db_path)
    print(f"date={args.date} resent=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

