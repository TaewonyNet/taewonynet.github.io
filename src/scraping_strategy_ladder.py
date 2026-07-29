#!/usr/bin/env python3
"""빠른 전략부터 순서대로 시도하다 봇월로 의심되면 다음 전략으로 폴백하는 PoC."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# 봇월 의심 판정에 쓰는 응답 특성. 실제로는 curl_cffi/playwright/StealthyFetcher 등을 쓴다.
_MIN_CONTENT_LEN = 80
_BLOCK_KEYWORDS = ("access denied", "captcha", "verify you are human")


@dataclass
class StrategyResult:
    name: str
    status: int = 0
    body: str = field(default="", repr=False)
    error: str = ""

    @property
    def suspected_bot_wall(self) -> bool:
        if self.error:
            return True
        if self.status in (401, 403, 429):
            return True
        if len(self.body) < _MIN_CONTENT_LEN:
            return True
        lowered = self.body[:2000].lower()
        return any(k in lowered for k in _BLOCK_KEYWORDS)


def _simple_get(url: str, headers: dict[str, str]) -> StrategyResult:
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return StrategyResult(name="", status=resp.status, body=body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return StrategyResult(name="", status=exc.code, body=body)
    except URLError as exc:
        return StrategyResult(name="", error=str(exc))


def strategy_plain(url: str) -> StrategyResult:
    """가장 가벼운 전략. 최소 헤더만 붙인다 (requests 단계에 해당)."""
    return _simple_get(url, {"User-Agent": "python-urllib"})


def strategy_browser_ua(url: str) -> StrategyResult:
    """브라우저 UA를 흉내낸 전략 (curl_cffi 단계에 해당)."""
    return _simple_get(
        url,
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Referer": "https://www.google.com/",
        },
    )


def strategy_full_headers(url: str) -> StrategyResult:
    """Accept/Accept-Language까지 채운 전략 (stealth 단계 흉내)."""
    return _simple_get(
        url,
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Referer": "https://www.google.com/",
            "X-Requested-With": "real-browser-session",
        },
    )


DEFAULT_LADDER: list[Callable[[str], StrategyResult]] = [
    strategy_plain,
    strategy_browser_ua,
    strategy_full_headers,
]


def fetch_with_ladder(
    url: str, strategies: list[Callable[[str], StrategyResult]] | None = None
) -> StrategyResult:
    """전략 목록을 순서대로 시도해 봇월로 의심되지 않는 첫 응답을 반환한다.

    모두 실패하면 마지막 결과를 반환한다(호출자가 suspected_bot_wall로 최종 판단).
    """
    strategies = strategies or DEFAULT_LADDER
    last = StrategyResult(name="none")
    for fn in strategies:
        result = fn(url)
        result.name = fn.__name__
        logger.info("시도 %s status=%s 봇월의심=%s", result.name, result.status, result.suspected_bot_wall)
        if not result.suspected_bot_wall:
            return result
        last = result
    return last


class _TieredGateHandler(BaseHTTPRequestHandler):
    """UA와 커스텀 헤더 유무에 따라 다른 단계에서만 통과시키는 데모 게이트."""

    def do_GET(self) -> None:  # noqa: N802
        ua = self.headers.get("User-Agent", "")
        xrw = self.headers.get("X-Requested-With", "")
        if "Chrome" in ua and xrw == "real-browser-session":
            self._respond(200, "<html><body>" + "실제 콘텐츠 " * 20 + "</body></html>")
        else:
            self._respond(403, "Access Denied: bot suspected")

    def _respond(self, status: int, body: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def _run_demo_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _TieredGateHandler)
    port = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(0.3)
    return server, f"http://127.0.0.1:{port}/"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    server, url = _run_demo_server()
    try:
        final = fetch_with_ladder(url)
        if final.suspected_bot_wall:
            print(f"모든 전략이 봇월로 의심됨. 마지막 전략: {final.name}")
        else:
            print(f"'{final.name}' 전략에서 통과 (status={final.status}, {len(final.body)}바이트)")
    finally:
        server.shutdown()
