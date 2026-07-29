"""
검색 인프라를 MCP(Model Context Protocol) 도구로 노출하는 최소 PoC.

fastmcp가 설치돼 있으면 실제 FastMCP 서버에 @app.tool()로 search/advanced_search/get_related
세 개를 등록한다. 없으면 딕셔너리 기반 ToolRegistry로 같은 등록 패턴을 흉내낸다.
여러 DB(문서 저장소·코드 저장소·이슈트래커)를 MultiRepository 하나로 묶어
LLM 에이전트 입장에서는 "도구 하나"만 보이게 감춘다.

독립 실행:
    python3 mcp_search_tool.py
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Callable

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("mcp_search_tool")

try:
    from fastmcp import FastMCP  # type: ignore

    HAS_FASTMCP = True
except ImportError:
    HAS_FASTMCP = False


@dataclass
class Repository:
    """단일 소스(DB)를 흉내내는 최소 저장소. 실제로는 sqlite/FTS·벡터 인덱스 등이 들어간다."""

    name: str
    documents: list[dict] = field(default_factory=list)

    def search(self, query: str, k: int = 5) -> list[dict]:
        hits = [d for d in self.documents if query.lower() in d["text"].lower()]
        return [{**d, "source": self.name} for d in hits[:k]]


class MultiRepository:
    """여러 Repository를 federation해 하나의 인터페이스 뒤에 감춘다.

    DB가 몇 개든, 어떤 종류든 상위 계층(MCP 도구)은 이 클래스 하나만 호출한다.
    """

    def __init__(self, repos: list[Repository]) -> None:
        self._repos = repos

    def search(self, query: str, k_per_repo: int = 3) -> list[dict]:
        merged: list[dict] = []
        for repo in self._repos:
            merged.extend(repo.search(query, k=k_per_repo))
        return merged

    def get_related(self, doc_id: str) -> list[dict]:
        # 데모: id 접두사가 같은 문서를 "관련 문서"로 취급한다.
        prefix = doc_id.split("-")[0]
        related = []
        for repo in self._repos:
            related.extend(
                {**d, "source": repo.name}
                for d in repo.documents
                if d["id"] != doc_id and d["id"].startswith(prefix)
            )
        return related


def _demo_repos() -> MultiRepository:
    docs_repo = Repository(
        name="docs",
        documents=[
            {"id": "doc-1", "text": "검색 인프라 아키텍처 개요 문서"},
            {"id": "doc-2", "text": "리랭킹 파이프라인 설계 노트"},
        ],
    )
    code_repo = Repository(
        name="code",
        documents=[
            {"id": "doc-3", "text": "search 함수 구현, 검색 인프라 코어 모듈"},
        ],
    )
    issue_repo = Repository(
        name="issues",
        documents=[
            {"id": "doc-4", "text": "검색 지연 이슈 트래킹"},
        ],
    )
    return MultiRepository([docs_repo, code_repo, issue_repo])


class FallbackToolRegistry:
    """fastmcp 없을 때 @app.tool() 등록 패턴을 흉내내는 최소 딕셔너리 레지스트리."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}

    def tool(self) -> Callable:
        def decorator(fn: Callable) -> Callable:
            self._tools[fn.__name__] = fn
            return fn

        return decorator

    def call(self, name: str, **kwargs) -> object:
        return self._tools[name](**kwargs)


def build_app(repo: MultiRepository):
    """search/advanced_search/get_related 세 도구를 등록한 app(또는 fallback registry)을 반환한다."""

    app = FastMCP("search-infra") if HAS_FASTMCP else FallbackToolRegistry()

    @app.tool()
    def search(query: str, k: int = 5) -> list[dict]:
        """소스 전체에서 query와 관련된 문서를 찾는다."""
        return repo.search(query, k_per_repo=k)

    @app.tool()
    def advanced_search(query: str, source: str | None = None, k: int = 5) -> list[dict]:
        """source를 지정하면 특정 저장소로 검색을 좁힌다."""
        results = repo.search(query, k_per_repo=k)
        if source:
            results = [r for r in results if r["source"] == source]
        return results

    @app.tool()
    def get_related(doc_id: str) -> list[dict]:
        """주어진 문서와 관련된 문서를 반환한다."""
        return repo.get_related(doc_id)

    return app


async def _call_search(app, query: str, k: int) -> list[dict]:
    """실제 FastMCP는 MCP 프로토콜(call_tool)을 통해서만 도구를 호출한다."""
    result = await app.call_tool("search", {"query": query, "k": k})
    return result.structured_content["result"]  # type: ignore[attr-defined]


def main() -> None:
    logger.info("fastmcp 설치 여부: %s", HAS_FASTMCP)
    repo = _demo_repos()
    app = build_app(repo)

    if HAS_FASTMCP:
        result = asyncio.run(_call_search(app, query="검색", k=3))
    else:
        result = app.call("search", query="검색", k=3)

    logger.info("search('검색') 결과 %d건", len(result))
    for r in result:
        logger.info("  [%s] %s", r["source"], r["text"])


if __name__ == "__main__":
    main()
