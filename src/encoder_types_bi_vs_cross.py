"""
bi-encoder vs cross-encoder 계산 횟수·소요 시간 비교 최소 PoC.

목(mock) bi-encoder는 문서마다 벡터를 한 번만 계산해 캐싱하고, 질의가 들어오면
질의 벡터 1회 계산 후 캐시된 문서 벡터와 비교만 한다. 목 cross-encoder는 질의와
문서를 한 쌍으로 묶어 매번 새로 "계산"하는 흉내를 낸다(인위적 지연 포함).

문서 100개 기준으로 두 방식의 계산 횟수와 총 소요 시간을 비교해,
"왜 검색은 bi-encoder로 하고 재정렬만 cross-encoder로 하는지"를 수치로 보여준다.

독립 실행:
    python3 encoder_types_bi_vs_cross.py
"""

from __future__ import annotations

import logging
import time

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("encoder_types_bi_vs_cross")

N_DOCS = 100
RERANK_TOP_K = 10  # cross-encoder는 검색 전체가 아니라 이 개수만 재정렬한다.

_BI_ENCODE_LATENCY = 0.0005   # 벡터 1개 계산 시 지연(문서 1건 또는 질의 1건)
_CROSS_SCORE_LATENCY = 0.003  # 질의-문서 쌍 1개 채점 시 지연(bi-encoder보다 훨씬 느림)


class MockBiEncoder:
    """문서 벡터를 한 번만 계산해 캐싱하는 목 bi-encoder."""

    def __init__(self) -> None:
        self.cache: dict[str, tuple[float, ...]] = {}
        self.encode_calls = 0

    def encode(self, text: str) -> tuple[float, ...]:
        """텍스트 1건을 벡터 1개로 인코딩한다(질의든 문서든 동일 함수)."""
        time.sleep(_BI_ENCODE_LATENCY)
        self.encode_calls += 1
        return (hash(text) % 1000 / 1000.0,)

    def index_documents(self, doc_ids: list[str]) -> None:
        """문서 벡터를 미리 계산해 캐시에 저장한다. 이후 질의마다 재계산하지 않는다."""
        for doc_id in doc_ids:
            self.cache[doc_id] = self.encode(doc_id)

    def search(self, query: str, doc_ids: list[str]) -> list[str]:
        """질의 벡터 1회만 새로 계산하고, 문서는 캐시된 벡터를 그대로 비교에 쓴다."""
        query_vec = self.encode(query)
        scored = [(doc_id, abs(query_vec[0] - self.cache[doc_id][0])) for doc_id in doc_ids]
        scored.sort(key=lambda x: x[1])
        return [doc_id for doc_id, _ in scored]


class MockCrossEncoder:
    """질의-문서 쌍마다 매번 새로 채점하는 목 cross-encoder."""

    def __init__(self) -> None:
        self.score_calls = 0

    def score(self, query: str, doc_id: str) -> float:
        """질의와 문서를 한 쌍으로 넣어 관련성 점수를 매번 새로 계산한다."""
        time.sleep(_CROSS_SCORE_LATENCY)
        self.score_calls += 1
        return hash((query, doc_id)) % 1000 / 1000.0

    def rerank(self, query: str, doc_ids: list[str]) -> list[str]:
        scored = [(doc_id, self.score(query, doc_id)) for doc_id in doc_ids]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in scored]


def main() -> None:
    doc_ids = [f"doc-{i}" for i in range(N_DOCS)]
    query = "검색 시스템 인코더 종류"

    # bi-encoder: 문서 100개 전체를 대상으로 검색.
    bi = MockBiEncoder()
    start = time.perf_counter()
    bi.index_documents(doc_ids)  # 문서당 1회 — 이후 질의가 몇 번 들어와도 재사용
    top_by_bi = bi.search(query, doc_ids)  # 질의당 1회 추가
    bi_elapsed = time.perf_counter() - start
    logger.info(
        "bi-encoder  : 문서 %d건 검색, 계산 %d회(문서 %d + 질의 1), %.3f초",
        N_DOCS, bi.encode_calls, N_DOCS, bi_elapsed,
    )

    # cross-encoder: bi-encoder가 추린 top-K만 재정렬(전체 100건을 재정렬하면 훨씬 느려짐).
    cross = MockCrossEncoder()
    candidates = top_by_bi[:RERANK_TOP_K]
    start = time.perf_counter()
    reranked = cross.rerank(query, candidates)
    cross_elapsed = time.perf_counter() - start
    logger.info(
        "cross-encoder: 후보 %d건 재정렬, 계산 %d회(질의x문서 쌍마다 1), %.3f초",
        RERANK_TOP_K, cross.score_calls, cross_elapsed,
    )

    # 비교용: cross-encoder로 문서 100건 전체를 처음부터 검색했다면 걸렸을 시간(가정치).
    hypothetical_full_calls = N_DOCS
    hypothetical_full_elapsed = hypothetical_full_calls * _CROSS_SCORE_LATENCY
    logger.info(
        "(참고) cross-encoder로 %d건 전체 검색 시 예상 계산 %d회, 약 %.3f초",
        N_DOCS, hypothetical_full_calls, hypothetical_full_elapsed,
    )

    print(f"\n결과: reranked top-{RERANK_TOP_K} = {reranked}")


if __name__ == "__main__":
    main()
