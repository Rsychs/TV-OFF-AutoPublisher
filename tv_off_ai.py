"""Small OpenAI-compatible client for the self-hosted FreeLLMAPI gateway.

The gateway owns provider selection and provider-level failover. This client
only retries transient gateway/network failures; it never logs credentials.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


class FreeLLMAPIError(RuntimeError):
    pass


def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.4,
    max_tokens: int = 700,
    timeout: int = 90,
) -> str:
    base_url = os.environ.get("FREELLMAPI_BASE_URL", "").strip().rstrip("/")
    api_key = os.environ.get("FREELLMAPI_API_KEY", "").strip()
    if not base_url or not api_key:
        raise FreeLLMAPIError(
            "Set FREELLMAPI_BASE_URL and FREELLMAPI_API_KEY in the environment."
        )
    if not (base_url.startswith("https://") or base_url.startswith("http://localhost")
            or base_url.startswith("http://127.0.0.1")):
        raise FreeLLMAPIError("FREELLMAPI_BASE_URL must use HTTPS (HTTP is allowed only for localhost).")

    endpoint = base_url if base_url.endswith("/v1/chat/completions") else base_url + "/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": model or os.environ.get("FREELLMAPI_MODEL", "auto"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise FreeLLMAPIError("Gateway returned an empty assistant response.")
            return content.strip()
        except urllib.error.HTTPError as exc:
            # Do not echo response bodies: some gateways include provider details.
            if exc.code not in RETRYABLE or attempt == 2:
                raise FreeLLMAPIError(f"FreeLLMAPI returned HTTP {exc.code}.") from None
            last_error = exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            if attempt == 2:
                raise FreeLLMAPIError(f"FreeLLMAPI request failed ({type(exc).__name__}).") from None
            last_error = exc
        time.sleep(2 ** attempt)
    raise FreeLLMAPIError(f"FreeLLMAPI request failed ({type(last_error).__name__ if last_error else 'unknown error'}).")


def main() -> int:
    prompt = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not prompt:
        print("Usage: python tv_off_ai.py 'prompt' (or pipe prompt on stdin)", file=sys.stderr)
        return 2
    try:
        answer = chat_completion([{"role": "user", "content": prompt}])
    except FreeLLMAPIError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
