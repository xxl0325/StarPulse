from __future__ import annotations

from starpulse.config import ConfigError, Settings, load_settings


def test_load_settings_defaults():
    settings = load_settings({})

    assert settings.top_n == 500
    assert settings.report_top_n == 20
    assert settings.timezone == "Asia/Shanghai"
    assert str(settings.sqlite_path) == "data/starpulse.sqlite3"
    assert settings.llm_provider == "openai-compatible"
    assert settings.dingtalk_keyword == "github"
    assert settings.github_daily_dataset == "githubarchive.day"


def test_load_settings_parses_overrides():
    settings = load_settings(
        {
            "TOP_N": "100",
            "REPORT_TOP_N": "10",
            "TIMEZONE": "UTC",
            "SQLITE_PATH": "/tmp/starpulse.sqlite3",
            "GCP_PROJECT": "demo-project",
            "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/creds.json",
            "GITHUB_TOKEN": "token",
            "LLM_PROVIDER": "openai-compatible",
            "LLM_BASE_URL": "https://example.com/v1",
            "LLM_API_KEY": "api-key",
            "LLM_MODEL": "gpt-4.1-mini",
            "DINGTALK_WEBHOOK_URL": "https://example.com/webhook",
            "DINGTALK_KEYWORD": "github",
            "DINGTALK_SECRET": "secret",
            "README_EXCERPT_CHARS": "4096",
            "GITHUB_API_BASE_URL": "https://api.github.example.com",
            "GITHUB_DAILY_DATASET": "custom.dataset",
        }
    )

    assert settings.top_n == 100
    assert settings.report_top_n == 10
    assert settings.timezone == "UTC"
    assert str(settings.sqlite_path) == "/tmp/starpulse.sqlite3"
    assert settings.gcp_project == "demo-project"
    assert str(settings.google_application_credentials) == "/tmp/creds.json"
    assert settings.github_token == "token"
    assert settings.llm_base_url == "https://example.com/v1"
    assert settings.llm_api_key == "api-key"
    assert settings.llm_model == "gpt-4.1-mini"
    assert settings.dingtalk_webhook_url == "https://example.com/webhook"
    assert settings.dingtalk_keyword == "github"
    assert settings.dingtalk_secret == "secret"
    assert settings.readme_excerpt_chars == 4096
    assert settings.github_api_base_url == "https://api.github.example.com"
    assert settings.github_daily_dataset == "custom.dataset"


def test_feature_requirements_raise_when_missing():
    settings = Settings()

    try:
        settings.require_bigquery()
    except ConfigError:
        pass
    else:
        raise AssertionError("expected ConfigError")
