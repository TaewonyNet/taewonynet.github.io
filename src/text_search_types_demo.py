"""
텍스트 검색 두 방식(키워드 vs 벡터) 비교 최소 PoC.

같은 질의 2개를 (a) 단순 키워드 부분일치 검색과 (b) 목(mock) 코사인 유사도
기반 벡터 검색에 각각 넣어, 정확한 단어 일치에 강한 질의와 동의어/의미
매칭에 강한 질의에서 결과가 어떻게 갈리는지 보여준다.

벡터는 실제 임베딩 모델 대신, 문서마다 사람이 미리 정해둔 "의미 좌표"를
고정 벡터로 부여해 코사인 유사도 계산 구조만 흉내낸다.

독립 실행:
    python3 text_search_types_demo.py
"""

from __future__ import annotations

import logging
import math

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("text_search_types_demo")

# 토이 문서 5개. 벡터는 (여행지, 음식, 기술) 3축 의미 좌표를 사람이 직접 부여했다.
DOCUMENTS = [
    {"id": "d1", "text": "제주도 여행 코스 추천", "vector": (0.95, 0.10, 0.05)},
    {"id": "d2", "text": "부산 관광 명소 정리", "vector": (0.80, 0.30, 0.10)},
    {"id": "d3", "text": "김치찌개 맛있게 끓이는 법", "vector": (0.05, 0.95, 0.05)},
    {"id": "d4", "text": "파이썬 리스트 컴프리헨션 사용법", "vector": (0.05, 0.05, 0.95)},
    {"id": "d5", "text": "SQLite 인덱스 설계 가이드", "vector": (0.05, 0.10, 0.90)},
]

# 질의 2개 + 각 질의의 의미 좌표(사람이 직접 부여, 벡터 검색용).
QUERIES = [
    {
        "text": "제주도",
        "vector": (0.95, 0.10, 0.05),
        "note": "정확한 단어 일치에 유리한 질의 — 문서 원문에 '제주도'가 그대로 있음",
    },
    {
        "text": "국내 여행지 어디가 좋을까",
        "vector": (0.85, 0.15, 0.05),
        "note": "동의어/의미 매칭에 유리한 질의 — 문서 원문에 겹치는 단어가 거의 없음",
    },
]


def keyword_search(query: str, documents: list[dict], top_k: int = 3) -> list[str]:
    """가장 단순한 키워드 부분일치 검색. 질의 단어가 문서 텍스트에 포함되는지만 본다."""
    hits = [doc["id"] for doc in documents if query in doc["text"]]
    return hits[:top_k]


def _cosine(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def vector_search(
    query_vector: tuple[float, float, float], documents: list[dict], top_k: int = 3
) -> list[tuple[str, float]]:
    """목 코사인 유사도 기반 벡터 검색. 문서마다 미리 정해둔 의미 좌표와 질의 좌표를 비교한다."""
    scored = [(doc["id"], _cosine(query_vector, doc["vector"])) for doc in documents]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def main() -> None:
    for query in QUERIES:
        logger.info("질의: %r (%s)", query["text"], query["note"])

        kw_hits = keyword_search(query["text"], DOCUMENTS)
        logger.info("  키워드 검색 결과: %s", kw_hits or "(없음)")

        vec_hits = vector_search(query["vector"], DOCUMENTS)
        vec_str = ", ".join(f"{doc_id}({score:.2f})" for doc_id, score in vec_hits)
        logger.info("  벡터 검색 결과  : %s", vec_str)
        print()


if __name__ == "__main__":
    main()
