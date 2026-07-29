#!/usr/bin/env python3
"""수집 유틸(ux.py류)을 MCP 도구 하나로 래핑하는 최소 PoC.

fastmcp가 설치돼 있으면 실제 FastMCP 서버로 `fetch_url` 도구를 등록한다.
없으면 같은 인터페이스를 흉내내는 간단한 함수 레지스트리로 대체해 등록
패턴 자체는 확인할 수 있게 한다.
"""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


def fetch_url(url: str, preview: int = 500) -> dict:
    """URL을 가져와 결과를 dict로 반환한다. 실제 프로젝트에서는 ux.fetch(url)로 대체한다.

    이 PoC에서는 외부 네트워크 대신 고정 응답을 흉내내 인터페이스만 보여준다.
    """
    fake_html = f"<html><body>fetched: {url}</body></html>"
    return {
        "ok": True,
        "method": "curl",
        "bytes": len(fake_html),
        "html": fake_html[:preview],
    }


class _FallbackToolRegistry:
    """fastmcp 없이도 '도구 등록' 패턴을 보여주는 최소 레지스트리."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: dict[str, Callable] = {}

    def tool(self, fn: Callable) -> Callable:
        self._tools[fn.__name__] = fn
        return fn

    def call(self, tool_name: str, **kwargs) -> dict:
        if tool_name not in self._tools:
            raise KeyError(f"등록되지 않은 도구: {tool_name}")
        return self._tools[tool_name](**kwargs)

    def list_tools(self) -> list[str]:
        return list(self._tools)


def build_server(name: str = "ux-fetch"):
    """fetch_url 하나를 도구로 등록한 서버(또는 대체 레지스트리)를 만든다."""
    try:
        from fastmcp import FastMCP
    except ImportError:
        logger.info("fastmcp 미설치 — 대체 레지스트리로 도구 등록 패턴만 보여준다.")
        server = _FallbackToolRegistry(name)
        server.tool(fetch_url)
        return server

    server = FastMCP(name)

    @server.tool
    def fetch_url_tool(url: str, preview: int = 500) -> dict:
        """URL을 수집해 method·bytes·html(preview)을 반환한다."""
        return fetch_url(url, preview=preview)

    return server


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    server = build_server()
    print(f"서버 타입: {type(server).__name__}")

    if isinstance(server, _FallbackToolRegistry):
        print(f"등록된 도구: {server.list_tools()}")
        result = server.call("fetch_url", url="https://example.com", preview=100)
    else:
        # FastMCP 서버는 실제로는 server.run()으로 구동한다. 데모에서는 등록된
        # 함수 로직만 직접 호출해 결과를 확인한다.
        result = fetch_url("https://example.com", preview=100)
        print("FastMCP 서버에 fetch_url_tool 도구가 등록됐다 (server.run()으로 구동).")

    print(f"결과: {result}")
