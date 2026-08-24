#!/usr/bin/env python3
"""Daily GLaDOS check-in. Cookie comes from GLADOS_COOKIE, never from source."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

CHECKIN_URL = "https://glados.rocks/api/user/checkin"
STATUS_URL = "https://glados.rocks/api/user/status"
DEFAULT_TOKEN = "glados.one"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def load_cookie() -> str:
    cookie = os.environ.get("GLADOS_COOKIE", "").strip().strip('"').strip("'")
    if not cookie:
        print("Missing GLADOS_COOKIE. Add it as a GitHub Actions secret.", file=sys.stderr)
        sys.exit(1)

    if "koa:sess=" not in cookie or "koa:sess.sig=" not in cookie:
        print(
            "GLADOS_COOKIE must look like: koa:sess=...; koa:sess.sig=...",
            file=sys.stderr,
        )
        sys.exit(1)
    return cookie


def request_json(url: str, cookie: str, payload: dict | None = None) -> tuple[int, object]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": USER_AGENT,
        "Cookie": cookie,
        "Origin": "https://glados.rocks",
        "Referer": "https://glados.rocks/console/checkin",
    }
    body = None
    method = "GET"
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
        method = "POST"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        status = err.code
    except urllib.error.URLError as err:
        raise SystemExit(f"Network error talking to GLaDOS: {err.reason}") from err

    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def remaining_days(status_payload: object) -> str | None:
    if not isinstance(status_payload, dict):
        return None
    data = status_payload.get("data") or {}
    left = data.get("leftDays")
    if left is None:
        return None
    try:
        return str(int(float(left)))
    except (TypeError, ValueError):
        return str(left)


def checkin_ok(http_status: int, payload: object) -> bool:
    if http_status >= 400:
        return False
    if not isinstance(payload, dict):
        return False

    code = payload.get("code")
    message = str(payload.get("message", "")).lower()
    if code in (0, 1):
        return True
    if any(token in message for token in ("checkin", "tomorrow", "got ", "success")):
        return True
    return False


def main() -> int:
    cookie = load_cookie()
    token = os.environ.get("GLADOS_TOKEN", DEFAULT_TOKEN).strip() or DEFAULT_TOKEN

    http_status, payload = request_json(CHECKIN_URL, cookie, {"token": token})
    print(f"Check-in HTTP {http_status}")
    if isinstance(payload, (dict, list)):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload)

    _, status_payload = request_json(STATUS_URL, cookie)
    days = remaining_days(status_payload)
    if days is not None:
        print(f"Remaining days: {days}")

    if checkin_ok(http_status, payload):
        return 0

    print("Check-in failed. Cookie may be expired, or the token may be wrong.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
