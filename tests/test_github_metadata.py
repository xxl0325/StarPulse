from __future__ import annotations

import base64

import pytest
import requests

from starpulse.github_metadata import (
    GitHubAPIError,
    build_github_headers,
    clean_readme_text,
    fetch_repo_metadata,
)


class FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers, timeout))
        return self.mapping[url]


class RaisingSession:
    def get(self, url, headers=None, timeout=None):
        raise requests.exceptions.SSLError("boom")


def test_clean_readme_text_drops_noise():
    text = """# Title\n\n![badge](https://example.com/badge.svg)\n\nTable of Contents\n- a\n- b\n\nReal content here.\n"""
    cleaned = clean_readme_text(text, 200)
    assert "badge" not in cleaned
    assert "Table of Contents" not in cleaned
    assert "Real content here." in cleaned


def test_fetch_repo_metadata(tmp_path):
    repo_url = "https://api.github.com/repos/acme/demo"
    readme_url = f"{repo_url}/readme"
    session = FakeSession(
        {
            repo_url: FakeResponse(
                200,
                {
                    "html_url": "https://github.com/acme/demo",
                    "description": "Demo project",
                    "language": "Python",
                    "topics": ["ai", "demo"],
                    "stargazers_count": 42,
                    "forks_count": 7,
                    "license": {"spdx_id": "MIT"},
                },
            ),
            readme_url: FakeResponse(
                200,
                {"content": base64.b64encode(b"# Demo\n\nUseful docs.\n").decode("utf-8"), "encoding": "base64"},
            ),
        }
    )

    metadata = fetch_repo_metadata(
        "acme/demo",
        token="token",
        session=session,
        readme_excerpt_chars=200,
    )
    assert metadata.repo_name == "acme/demo"
    assert metadata.html_url == "https://github.com/acme/demo"
    assert metadata.description == "Demo project"
    assert metadata.language == "Python"
    assert metadata.topics_json == '["ai", "demo"]'
    assert metadata.license == "MIT"
    assert metadata.readme_excerpt == "# Demo\n\nUseful docs."


def test_fetch_repo_metadata_raises_for_missing_repo():
    repo_url = "https://api.github.com/repos/acme/missing"
    session = FakeSession({repo_url: FakeResponse(404, {})})
    with pytest.raises(GitHubAPIError):
        fetch_repo_metadata("acme/missing", session=session)


def test_fetch_repo_metadata_wraps_request_errors():
    with pytest.raises(GitHubAPIError):
        fetch_repo_metadata("acme/demo", session=RaisingSession())


def test_build_github_headers_includes_token():
    headers = build_github_headers("token")
    assert headers["Authorization"] == "Bearer token"
