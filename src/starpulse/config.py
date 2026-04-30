from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os

from dotenv import load_dotenv


class ConfigError(ValueError):
    pass


def _get_int(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{key} must be an integer") from exc


def _get_path(env: Mapping[str, str], key: str, default: Path) -> Path:
    value = env.get(key)
    return Path(value) if value else default


@dataclass(frozen=True, slots=True)
class Settings:
    top_n: int = 500
    report_top_n: int = 20
    timezone: str = "Asia/Shanghai"
    sqlite_path: Path = Path("data/starpulse.sqlite3")
    gcp_project: str | None = None
    google_application_credentials: Path | None = None
    github_token: str | None = None
    llm_provider: str = "openai-compatible"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str | None = None
    llm_model: str | None = None
    dingtalk_webhook_url: str | None = None
    dingtalk_keyword: str | None = "github"
    dingtalk_secret: str | None = None
    readme_excerpt_chars: int = 6000
    github_api_base_url: str = "https://api.github.com"
    github_daily_dataset: str = "githubarchive.day"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        return cls(
            top_n=_get_int(env, "TOP_N", 500),
            report_top_n=_get_int(env, "REPORT_TOP_N", 20),
            timezone=env.get("TIMEZONE", "Asia/Shanghai"),
            sqlite_path=_get_path(env, "SQLITE_PATH", Path("data/starpulse.sqlite3")),
            gcp_project=env.get("GCP_PROJECT") or None,
            google_application_credentials=_get_path(
                env,
                "GOOGLE_APPLICATION_CREDENTIALS",
                Path(""),
            )
            if env.get("GOOGLE_APPLICATION_CREDENTIALS")
            else None,
            github_token=env.get("GITHUB_TOKEN") or None,
            llm_provider=env.get("LLM_PROVIDER", "openai-compatible"),
            llm_base_url=env.get("LLM_BASE_URL", "https://api.openai.com/v1"),
            llm_api_key=env.get("LLM_API_KEY") or None,
            llm_model=env.get("LLM_MODEL") or None,
            dingtalk_webhook_url=env.get("DINGTALK_WEBHOOK_URL") or None,
            dingtalk_keyword=env.get("DINGTALK_KEYWORD") or "github",
            dingtalk_secret=env.get("DINGTALK_SECRET") or None,
            readme_excerpt_chars=_get_int(env, "README_EXCERPT_CHARS", 6000),
            github_api_base_url=env.get("GITHUB_API_BASE_URL", "https://api.github.com"),
            github_daily_dataset=env.get("GITHUB_DAILY_DATASET", "githubarchive.day"),
        )

    def require_bigquery(self) -> None:
        if not self.gcp_project:
            raise ConfigError("GCP_PROJECT is required for BigQuery import")

    def require_github(self) -> None:
        if not self.github_token:
            raise ConfigError("GITHUB_TOKEN is required for GitHub metadata fetch")

    def require_llm(self) -> None:
        if not self.llm_api_key or not self.llm_model:
            raise ConfigError("LLM_API_KEY and LLM_MODEL are required for report generation")

    def require_dingtalk(self) -> None:
        if not self.dingtalk_webhook_url:
            raise ConfigError("DINGTALK_WEBHOOK_URL is required for DingTalk delivery")


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    if env is None:
        load_dotenv()
    return Settings.from_env(env)
