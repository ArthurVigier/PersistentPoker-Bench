from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def post_json(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **({} if headers is None else headers),
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Local model HTTP {exc.code} from {url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach local model endpoint {url}: {exc}") from exc
    if not body:
        return {}
    decoded = json.loads(body)
    if not isinstance(decoded, dict):
        raise ValueError(f"Expected JSON object from local model endpoint {url}.")
    return decoded


def join_url(base_url: str, suffix: str) -> str:
    return f"{base_url.rstrip('/')}/{suffix.lstrip('/')}"
