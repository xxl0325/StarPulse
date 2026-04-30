from __future__ import annotations

from starpulse.llm_provider import LLMProviderError, OpenAICompatibleProvider


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_openai_compatible_provider_builds_request(monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(200, {"choices": [{"message": {"content": "# report"}}]})

    monkeypatch.setattr("starpulse.llm_provider.requests.post", fake_post)
    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        api_key="secret",
        model="gpt-4.1-mini",
    )
    report = provider.generate(system_prompt="rules", payload={"hello": "world"})

    assert report == "# report"
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["json"]["model"] == "gpt-4.1-mini"
    assert captured["json"]["messages"][0]["role"] == "system"


def test_openai_compatible_provider_raises_on_bad_response(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(500, {})

    monkeypatch.setattr("starpulse.llm_provider.requests.post", fake_post)
    provider = OpenAICompatibleProvider(
        base_url="https://api.openai.com/v1",
        api_key="secret",
        model="gpt-4.1-mini",
    )
    try:
        provider.generate(system_prompt="rules", payload={"hello": "world"})
    except LLMProviderError:
        pass
    else:
        raise AssertionError("expected LLMProviderError")

