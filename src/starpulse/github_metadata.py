from __future__ import annotations

import base64
import json
import re
from typing import Any, Mapping

import requests
from requests import RequestException

from .storage import RepoMetadata


class GitHubAPIError(RuntimeError):
    pass


_BADGE_LINE = re.compile(r"(!\[.*\]\(.*\)|\[!\[.*\]\(.*\))")
_TOC_LINE = re.compile(r"^(#+\s*)?(table of contents|contents|toc)\s*$", re.IGNORECASE)


def build_github_headers(token: str | None) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def clean_readme_text(text: str, max_chars: int) -> str:
    cleaned_lines: list[str] = []
    seen_content = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        if _BADGE_LINE.search(line):
            continue
        if _TOC_LINE.match(line):
            continue
        if line.startswith("![") or line.startswith("[!["):
            continue
        if line.lower().startswith("<!--"):
            continue
        cleaned_lines.append(line)
        seen_content = True

    cleaned = "\n".join(cleaned_lines).strip()
    if not seen_content:
        cleaned = text.strip()
    return cleaned[:max_chars]


def _decode_readme_content(payload: Mapping[str, Any]) -> str | None:
    content = payload.get("content")
    encoding = payload.get("encoding")
    if not content or encoding != "base64":
        return None
    decoded = base64.b64decode(content)
    return decoded.decode("utf-8", errors="replace")


def fetch_repo_metadata(
    full_name: str,
    *,
    token: str | None = None,
    base_url: str = "https://api.github.com",
    readme_excerpt_chars: int = 6000,
    session: requests.Session | None = None,
) -> RepoMetadata:
    http = session or requests.Session()
    headers = build_github_headers(token)

    repo_url = f"{base_url.rstrip('/')}/repos/{full_name}"
    try:
        repo_resp = http.get(repo_url, headers=headers, timeout=30)
    except RequestException as exc:
        raise GitHubAPIError(f"failed to fetch repository metadata: {full_name}") from exc
    if repo_resp.status_code == 404:
        raise GitHubAPIError(f"repository not found: {full_name}")
    if repo_resp.status_code >= 400:
        raise GitHubAPIError(f"failed to fetch repository metadata: {full_name} ({repo_resp.status_code})")

    repo = repo_resp.json()
    topics = repo.get("topics") or []
    license_info = repo.get("license") or {}
    html_url = repo.get("html_url") or f"https://github.com/{full_name}"

    readme_excerpt = None
    readme_url = f"{repo_url}/readme"
    try:
        readme_resp = http.get(readme_url, headers=headers, timeout=30)
    except RequestException:
        readme_resp = None
    if readme_resp is not None and readme_resp.status_code == 200:
        readme_payload = readme_resp.json()
        raw_readme = _decode_readme_content(readme_payload)
        if raw_readme:
            readme_excerpt = clean_readme_text(raw_readme, readme_excerpt_chars)
    elif readme_resp is not None and readme_resp.status_code not in {404, 403}:
        raise GitHubAPIError(f"failed to fetch README: {full_name} ({readme_resp.status_code})")

    return RepoMetadata(
        repo_name=full_name,
        html_url=html_url,
        description=repo.get("description"),
        language=repo.get("language"),
        topics_json=json.dumps(topics, ensure_ascii=False),
        stars=repo.get("stargazers_count"),
        forks=repo.get("forks_count"),
        license=(license_info.get("spdx_id") or license_info.get("name")),
        readme_excerpt=readme_excerpt,
    )
