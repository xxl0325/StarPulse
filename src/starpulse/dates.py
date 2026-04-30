from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from zoneinfo import ZoneInfo


_BqSuffix = re.compile(r"^\d{8}$")


class DateFormatError(ValueError):
    pass


def parse_ymd(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise DateFormatError("date must use YYYY-MM-DD") from exc


def normalize_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return parse_ymd(value)


def yesterday_in_timezone(timezone: str, now: datetime | None = None) -> date:
    tz = ZoneInfo(timezone)
    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz)
    local = current.astimezone(tz)
    return (local - timedelta(days=1)).date()


def bq_table_suffix(value: str | date) -> str:
    normalized = normalize_date(value)
    return normalized.strftime("%Y%m%d")


def validate_bq_suffix(value: str) -> str:
    if not _BqSuffix.fullmatch(value):
        raise DateFormatError("BigQuery suffix must be YYYYMMDD")
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise DateFormatError("BigQuery suffix is not a valid calendar date") from exc
    return value


def bq_table_name_for_date(value: str | date, dataset: str = "githubarchive.day") -> str:
    return f"{dataset}.{bq_table_suffix(value)}"


@dataclass(frozen=True, slots=True)
class DateWindow:
    start: date
    end: date

    def iter_days(self):
        current = self.start
        while current <= self.end:
            yield current
            current += timedelta(days=1)

