from __future__ import annotations

import pytest

from scripts.run_daily_pipeline import main


def test_main_rejects_invalid_date_before_running_pipeline():
    with pytest.raises(SystemExit) as exc_info:
        main(["--date", "2026-04-29; echo leaked"])

    assert str(exc_info.value) == "date must use YYYY-MM-DD"
