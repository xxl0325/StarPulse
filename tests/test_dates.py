from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from starpulse.dates import (
    DateFormatError,
    bq_table_name_for_date,
    bq_table_suffix,
    parse_ymd,
    validate_bq_suffix,
    yesterday_in_timezone,
)


def test_yesterday_in_timezone_uses_local_day():
    now = datetime(2026, 4, 30, 1, 0, tzinfo=ZoneInfo("UTC"))
    assert yesterday_in_timezone("Asia/Shanghai", now=now).isoformat() == "2026-04-29"


def test_bq_helpers():
    assert bq_table_suffix("2026-04-29") == "20260429"
    assert bq_table_name_for_date("2026-04-29") == "githubarchive.day.20260429"
    assert validate_bq_suffix("20260429") == "20260429"
    assert parse_ymd("2026-04-29").isoformat() == "2026-04-29"


@pytest.mark.parametrize("value", ["2026-4-29", "2026042", "abc", "20261301"])
def test_validate_bq_suffix_rejects_invalid_values(value):
    with pytest.raises(DateFormatError):
        validate_bq_suffix(value)

