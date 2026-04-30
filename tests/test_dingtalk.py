from __future__ import annotations

from starpulse.dingtalk import (
    DingTalkError,
    DingTalkClient,
    build_keyword_webhook_url,
    build_signed_webhook_url,
)


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_build_signed_webhook_url_contains_timestamp_and_sign():
    url = build_signed_webhook_url("https://example.com/webhook", "secret", timestamp_ms=1234567890000)
    assert "timestamp=1234567890000" in url
    assert "sign=" in url


def test_build_keyword_webhook_url_contains_keyword():
    url = build_keyword_webhook_url("https://example.com/webhook", "github")
    assert "keyword=github" in url


def test_send_markdown(monkeypatch):
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse(200, {"errcode": 0, "errmsg": "ok"})

    monkeypatch.setattr("starpulse.dingtalk.requests.post", fake_post)
    client = DingTalkClient("https://example.com/webhook", keyword="github")
    data = client.send_markdown("title", "# report")
    assert data["errcode"] == 0
    assert captured["json"]["msgtype"] == "markdown"
    assert "github" in captured["json"]["markdown"]["text"].lower()
    assert "keyword=github" in captured["url"]


def test_send_markdown_raises_on_error(monkeypatch):
    def fake_post(url, json=None, timeout=None):
        return FakeResponse(200, {"errcode": 400})

    monkeypatch.setattr("starpulse.dingtalk.requests.post", fake_post)
    client = DingTalkClient("https://example.com/webhook", keyword="github")
    try:
        client.send_markdown("title", "# report")
    except DingTalkError:
        pass
    else:
        raise AssertionError("expected DingTalkError")
