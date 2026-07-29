#!/usr/bin/env python3
"""유료 검색 API 없이 웹 검색 결과를 LLM 그라운딩용 컨텍스트로 만드는 2단계 폴백.

1) DuckDuckGo HTML 라이트 엔드포인트(`html.duckduckgo.com/html/`)를 requests로
   호출해 결과를 파싱한다.
2) 네트워크 오류·차단·파싱 실패 시 목(mock) fetch 함수로 폴백해 오프라인에서도
   동일한 인터페이스로 검색 결과 스니펫 리스트를 반환한다.

requirements: requests (없으면 mock 경로만 동작), 표준 라이브러리 html.parser
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from html.parser import HTMLParser

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"


@dataclass
class SearchResult:
    title: str
    snippet: str
    url: str


class _DuckDuckGoResultParser(HTMLParser):
    """DuckDuckGo HTML 결과 페이지에서 `result__a`(제목+링크) 텍스트를 추출한다.

    실제 페이지 구조는 자주 바뀌므로, 여기서는 데모 목적의 단순화된 파서다.
    a 태그 중 class에 result__a가 포함된 것만 제목/링크 후보로 모은다.
    """

    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_result_link = False
        self._current_href = ""
        self._current_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attr_dict = dict(attrs)
        cls = attr_dict.get("class") or ""
        if "result__a" in cls:
            self._in_result_link = True
            self._current_href = attr_dict.get("href") or ""
            self._current_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_link:
            self._in_result_link = False
            if self._current_text.strip():
                self.results.append(
                    SearchResult(
                        title=self._current_text.strip(),
                        snippet="",
                        url=self._current_href,
                    )
                )

    def handle_data(self, data: str) -> None:
        if self._in_result_link:
            self._current_text += data


def _fetch_duckduckgo(query: str, timeout: float = 5.0) -> list[SearchResult]:
    """DuckDuckGo HTML 엔드포인트를 호출해 검색 결과를 파싱한다.

    requests 미설치이거나 네트워크 실패 시 예외를 그대로 올린다.
    호출부(`search_and_ground`)가 이를 잡아 mock 폴백으로 넘어간다.
    """
    import requests  # 지연 임포트: 미설치 환경에서도 모듈 로드가 되게 한다

    resp = requests.get(
        DUCKDUCKGO_URL,
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
    )
    resp.raise_for_status()
    parser = _DuckDuckGoResultParser()
    parser.feed(resp.text)
    if not parser.results:
        raise ValueError("DuckDuckGo 결과 파싱 실패: 결과 0건")
    return parser.results[:5]


def _mock_fetch(query: str) -> list[SearchResult]:
    """오프라인 데모·네트워크 실패 시 사용하는 목 검색 결과."""
    logger.info("mock fetch 폴백 사용: query=%r", query)
    return [
        SearchResult(
            title=f"{query} 관련 최신 동향 정리",
            snippet=f"'{query}'에 대한 2026년 기준 요약 스니펫. (mock 데이터)",
            url="https://example.com/mock-result-1",
        ),
        SearchResult(
            title=f"{query} 공식 문서",
            snippet=f"'{query}' 관련 공식 레퍼런스 발췌. (mock 데이터)",
            url="https://example.com/mock-result-2",
        ),
    ]


def search_and_ground(query: str) -> list[SearchResult]:
    """검색을 수행해 LLM 컨텍스트 주입용 스니펫 리스트를 반환한다.

    1차: DuckDuckGo HTML 파싱. 2차(예외 발생 시): mock 폴백.
    반환된 리스트가 비어 있지 않다는 것만 보장하며, 실패 원인은 로그로 남긴다.
    """
    try:
        results = _fetch_duckduckgo(query)
        logger.info("DuckDuckGo 검색 성공: %d건", len(results))
        return results
    except Exception as exc:  # noqa: BLE001 - 네트워크/파싱 실패를 폭넓게 흡수해 폴백
        logger.warning("DuckDuckGo 검색 실패(%s) -> mock 폴백", exc)
        return _mock_fetch(query)


def build_grounding_prompt(query: str, results: list[SearchResult]) -> str:
    """검색 결과를 LLM 시스템 프롬프트에 넣을 블록 텍스트로 조립한다."""
    lines = [f"다음은 '{query}'에 대한 검색 결과다. 참고해 답하라.", ""]
    for i, r in enumerate(results, start=1):
        lines.append(f"{i}. {r.title} ({r.url})")
        if r.snippet:
            lines.append(f"   {r.snippet}")
    return "\n".join(lines)


if __name__ == "__main__":
    query = "2026년 LLM 컨텍스트 압축 기법"
    results = search_and_ground(query)
    prompt_block = build_grounding_prompt(query, results)
    print(f"검색 결과 {len(results)}건")
    print(prompt_block)
