from __future__ import annotations

from starpulse.report_builder import build_daily_report_payload, render_fallback_report, render_provider_prompt_payload
from starpulse.storage import RepoMetadata


def test_build_daily_report_payload_merges_metadata():
    payload = build_daily_report_payload(
        date="2026-04-29",
        top20_rows=[
            {"rank": 1, "repo_name": "a/repo", "star_delta": 10, "html_url": "https://github.com/a/repo"}
        ],
        burst_rows=[
            {"repo_name": "a/repo", "burst_score": 8, "yesterday_stars": 10, "html_url": "https://github.com/a/repo"}
        ],
        metadata_by_repo={
            "a/repo": RepoMetadata(
                repo_name="a/repo",
                html_url="https://github.com/a/repo",
                description="demo project",
                language="Python",
                topics_json='["demo", "ai"]',
                stars=99,
                forks=7,
                license="MIT",
                readme_excerpt="demo readme",
            )
        },
    )

    assert payload["overview"]["top20_total_star_delta"] == 10
    assert payload["top20"][0]["language"] == "Python"
    assert payload["top20"][0]["readme_available"] is True
    assert payload["burst_top5"][0]["topics"] == ["demo", "ai"]


def test_render_fallback_report_contains_tables():
    payload = build_daily_report_payload(
        date="2026-04-29",
        top20_rows=[
            {"rank": 1, "repo_name": "a/repo", "star_delta": 10, "html_url": "https://github.com/a/repo"}
        ],
        burst_rows=[],
        metadata_by_repo={},
    )
    markdown = render_fallback_report(payload)
    assert "## Top20" in markdown
    assert "a/repo" in markdown
    assert "## 突然爆发 Top5" in markdown
    assert "信息不足" in markdown


def test_render_provider_prompt_payload_is_structured():
    payload = build_daily_report_payload(
        date="2026-04-29",
        top20_rows=[],
        burst_rows=[],
        metadata_by_repo={},
    )
    prompt_payload = render_provider_prompt_payload(payload)
    assert set(prompt_payload) == {"date", "overview", "top20", "burst_top5"}

