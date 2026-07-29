#!/usr/bin/env python3
"""User-Agent/헤더 조합을 순회하며 기본적인 봇 차단 통과 여부를 판정하는 PoC."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# 차단 여부 판정에 쓰는 응답 본문 서명. 실제 봇 차단 페이지에 흔히 등장하는 문자열이다.
_BLOCK_SIGNATURES = ("access denied", "blocked", "captcha", "verify you are human")

# 빠른 것부터 강한 것 순으로 시도할 헤더 조합.
HEADER_SETS: list[dict[str, str]] = [
    {"User-Agent": "python-requests/2.x"},
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "Referer": "https://www.google.com/",
    },
]


@dataclass
class FetchAttempt:
    headers: dict[str, str]
    status: int = 0
    blocked: bool = False
    error: str = ""
    body: str = field(default="", repr=False)


def _looks_blocked(status: int, body: str) -> bool:
    if status in (401, 403, 429):
        return True
    lowered = body[:2000].lower()
    return any(sig in lowered for sig in _BLOCK_SIGNATURES)


def fetch_with_header_rotation(url: str, header_sets: list[dict[str, str]] | None = None) -> FetchAttempt:
    """header_sets를 순서대로 시도해 처음으로 차단되지 않은 응답을 반환한다.

    모든 조합이 차단되면 마지막 시도 결과를 그대로 반환한다(호출자가 blocked로 판단).
    """
    header_sets = header_sets or HEADER_SETS
    last = FetchAttempt(headers={})
    for headers in header_sets:
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                status = resp.status
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            status = exc.code
        except URLError as exc:
            last = FetchAttempt(headers=headers, error=str(exc))
            continue

        blocked = _looks_blocked(status, body)
        attempt = FetchAttempt(headers=headers, status=status, blocked=blocked, body=body)
        logger.info("시도 UA=%s status=%s blocked=%s", headers.get("User-Agent", "-")[:30], status, blocked)
        if not blocked:
            return attempt
        last = attempt
    return last


class _GateHandler(BaseHTTPRequestHandler):
    """단순 UA 검사만 하는 데모 게이트. python-requests UA는 차단하고 브라우저 UA만 통과시킨다."""

    def do_GET(self) -> None:  # noqa: N802
        ua = self.headers.get("User-Agent", "")
        if "Chrome" not in ua:
            self.send_response(403)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Access Denied: bot suspected".encode("utf-8"))
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<html><body>OK</body></html>".encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def _run_demo_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _GateHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    return server, f"http://127.0.0.1:{port}/"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    server, url = _run_demo_server()
    try:
        result = fetch_with_header_rotation(url)
        if result.blocked:
            print(f"모든 헤더 조합이 차단됐다. 마지막 상태: {result.status}")
        else:
            print(f"통과한 헤더: {result.headers} (status={result.status})")
    finally:
        server.shutdown()
