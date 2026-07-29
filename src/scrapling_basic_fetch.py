#!/usr/bin/env python3
"""scrapling Fetcher로 URL을 가져와 텍스트/셀렉터를 추출하는 최소 PoC."""

from __future__ import annotations

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

logger = logging.getLogger(__name__)

_DEMO_HTML = (
    "<html><body>"
    "<h1 class=\"title\">데모 페이지</h1>"
    "<p class=\"desc\">scrapling Fetcher 최소 사용 예시</p>"
    "</body></html>"
)


def fetch_and_extract(url: str, css_selector: Optional[str] = None) -> str:
    """scrapling Fetcher로 url을 가져와 css_selector에 해당하는 텍스트를 추출한다.

    scrapling이 설치되어 있지 않으면 설치 안내를 담은 RuntimeError를 던진다.
    셀렉터를 넘기지 않으면 페이지 전체 텍스트를 반환한다.
    """
    try:
        from scrapling.fetchers import Fetcher
    except ImportError as exc:
        raise RuntimeError(
            "scrapling이 설치되어 있지 않다. `pip install scrapling` 후 다시 실행한다."
        ) from exc

    page = Fetcher.get(url)
    if css_selector:
        nodes = page.css(css_selector)
        return "\n".join(n.text for n in nodes if n.text)
    return page.get_all_text()


class _DemoHandler(BaseHTTPRequestHandler):
    """로컬 데모용 최소 HTTP 핸들러. 실제 사이트 대신 자족 실행을 위해 사용한다."""

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler 규약)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_DEMO_HTML.encode("utf-8"))

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return  # 데모 중 콘솔 소음 억제


def _run_demo_server() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), _DemoHandler)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    return server, f"http://127.0.0.1:{port}/"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    server, url = _run_demo_server()
    try:
        title = fetch_and_extract(url, css_selector=".title")
        print(f"셀렉터 추출 결과: {title}")

        full_text = fetch_and_extract(url)
        print(f"전체 텍스트: {full_text!r}")
    except RuntimeError as exc:
        print(f"[안내] {exc}")
    finally:
        server.shutdown()
