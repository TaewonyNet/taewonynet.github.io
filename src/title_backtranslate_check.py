#!/usr/bin/env python3
"""어색한 한국어 문구를 영문으로 번역했다가 다시 한국어로 역번역해 나란히 보여준다.

원본 -> 영문 -> 역번역(개선안) 세 줄을 함께 출력하면 "이 표현이 정말 말하는
것"과 "내가 쓴 것"의 간극이 드러난다. 실제 번역 API 키가 없는 환경에서도
데모가 돌아가도록, 기본 `translate_fn`은 이 블로그의 실제 제목 개선 사례를
그대로 담은 간단한 사전 치환 mock이다.

실전에서 쓰려면 `translate_fn`을 실제 번역기로 바꾸면 된다. 예:
    from googletrans import Translator
    translator = Translator()
    def real_translate_fn(text: str) -> tuple[str, str]:
        en = translator.translate(text, src="ko", dest="en").text
        ko = translator.translate(en, src="en", dest="ko").text
        return en, ko
    backtranslate("원본 문구", translate_fn=real_translate_fn)

requirements: 표준 라이브러리만 (실제 번역기 연결 시 googletrans 등 선택)
"""
from __future__ import annotations

import logging
from typing import Callable

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TranslateFn = Callable[[str], tuple[str, str]]

# 실제 블로그 제목 7개 역번역 사례 — mock 번역기의 사전
_MOCK_TABLE: dict[str, tuple[str, str]] = {
    "스크래핑이 안될 경우에 대한 연구": (
        "Research on what to do when scraping fails",
        "스크래핑이 막혔을 때 대안을 찾아보자",
    ),
    "CORS의 정의 및 예외 분석": (
        "Understanding CORS and analyzing exception scenarios",
        "CORS가 뭔지, 언제 예외가 생기는지 분석해보자",
    ),
    "북마크릿이란 무엇인가": (
        "What is a bookmarklet?",
        "북마크릿이 뭔지 알아보자",
    ),
    "dbt처럼 LLM 생성 변환을 안전하게 실행하는 샌드박스": (
        "A sandbox for safely running LLM-generated transformations like dbt",
        "LLM이 만든 변환 코드를 dbt처럼 안전하게 실행해보자",
    ),
    "워킹트리·git 히스토리를 훑는 비밀유출 감사 게이트": (
        "A secret leak audit gate that scans the worktree and git history",
        "워킹트리와 git 히스토리를 훑어 비밀 유출을 막아보자",
    ),
    "LLM 검증자를 self가 아닌 cross로 분리해보자": (
        "Separate LLM validators to cross-validate instead of self-validate",
        "LLM 결과를 같은 모델이 아닌 다른 모델로 교차 검증해보자",
    ),
    "federation 검색의 rerank 과부하를 풀에 분배해보자": (
        "Distribute reranking load from federated search across a worker pool",
        "여러 소스 통합 검색의 리랭킹 부하를 워커 풀로 분산해보자",
    ),
}


def mock_translate_fn(text: str) -> tuple[str, str]:
    """사전에 있는 문구는 실제 사례를, 없는 문구는 표시용 placeholder를 반환한다."""
    if text in _MOCK_TABLE:
        return _MOCK_TABLE[text]
    logger.warning("사전에 없는 문구 — placeholder로 대체: %s", text)
    return f"[EN] {text}", f"[역번역] {text}"


def backtranslate(korean_text: str, translate_fn: TranslateFn = mock_translate_fn) -> dict:
    """원본·영문·역번역(개선안)을 함께 담아 반환한다."""
    english, roundtrip = translate_fn(korean_text)
    return {"original": korean_text, "english": english, "roundtrip": roundtrip}


def print_comparison(results: list[dict]) -> None:
    """표 형태로 원본/영문/개선안을 나란히 출력한다."""
    print(f"{'원본':<45} {'영문':<55} 개선")
    print("-" * 130)
    for r in results:
        print(f"{r['original']:<45} {r['english']:<55} {r['roundtrip']}")


if __name__ == "__main__":
    titles = list(_MOCK_TABLE.keys())
    results = [backtranslate(title) for title in titles]
    print_comparison(results)

    # 사전에 없는 새 문구도 같은 함수로 처리 가능 (mock은 placeholder만 반환)
    unseen = backtranslate("에이전트 워크플로우를 재구성해보았다")
    print("\n사전에 없는 문구 처리 예시:")
    print(unseen)
