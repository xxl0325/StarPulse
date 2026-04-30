from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import hmac
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Any

import requests


class DingTalkError(RuntimeError):
    pass


def _merge_query_params(webhook_url: str, params: dict[str, str]) -> str:
    parts = urlsplit(webhook_url)
    existing = dict(parse_qsl(parts.query, keep_blank_values=True))
    existing.update({key: value for key, value in params.items() if value})
    query = urlencode(existing)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def build_keyword_webhook_url(webhook_url: str, keyword: str) -> str:
    return _merge_query_params(webhook_url, {"keyword": keyword})


def build_signed_webhook_url(webhook_url: str, secret: str, *, timestamp_ms: int | None = None) -> str:
    timestamp = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), string_to_sign, hashlib.sha256).digest()
    sign = base64.b64encode(digest).decode("utf-8")
    return _merge_query_params(webhook_url, {"timestamp": str(timestamp), "sign": sign})


@dataclass(frozen=True, slots=True)
class DingTalkClient:
    webhook_url: str
    keyword: str | None = "github"
    secret: str | None = None
    timeout: int = 30

    def _url(self) -> str:
        if self.secret:
            return build_signed_webhook_url(self.webhook_url, self.secret)
        if self.keyword:
            return build_keyword_webhook_url(self.webhook_url, self.keyword)
        return self.webhook_url

    def _decorate_markdown(self, markdown: str) -> str:
        if not self.keyword:
            return markdown
        if self.keyword.lower() in markdown.lower():
            return markdown
        return f"关键词：{self.keyword}\n\n{markdown}"

    def send_markdown(self, title: str, markdown: str) -> dict[str, Any]:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": self._decorate_markdown(markdown),
            },
        }
        response = requests.post(self._url(), json=payload, timeout=self.timeout)
        if response.status_code >= 400:
            raise DingTalkError(f"DingTalk request failed with status {response.status_code}")
        data = response.json()
        if data.get("errcode") != 0:
            raise DingTalkError(f"DingTalk returned error: {data}")
        return data
