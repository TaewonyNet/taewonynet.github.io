"""
리랭크(재정렬) 세 방식 중 "결과 리스트 결합" 두 가지를 비교하는 최소 PoC.

같은 질의에 대해 두 검색기가 서로 다른 척도의 점수로 결과를 낸다고 가정한다.
    - 벡터 검색: 코사인 유사도, 0~1
    - 키워드 검색(BM25류): 0~20 범위의 점수

이 둘을 하나의 순위로 합치는 두 가지 방법을 각각 구현해 최종 순위가
어떻게 달라지는지 비교한다.

    (a) RRF(Reciprocal Rank Fusion): 점수를 보지 않고 "순위"만으로 결합한다.
        척도가 달라도 그대로 쓸 수 있어 정규화가 필요 없다.
    (b) 정규화 후 가중합(weighted score fusion): 각 리스트를 0~1로 min-max
        정규화한 뒤 가중치를 곱해 더한다. RRF보다 세밀하게 조정할 수 있지만
        정규화 방식과 가중치를 튜닝해야 한다.

cross-encoder 리랭크(질의+문서를 함께 넣어 정밀 점수를 매기는 방식)는
계산 비용이 높아 소수 후보에만 적용하는 게 보통이라 이 PoC의 범위 밖이다.
개념은 이 글의 §2에서 표로만 정리한다.

독립 실행:
    python3 rerank_types_demo.py
"""
from __future__ import annotations

import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("rerank_types_demo")

# 벡터 검색 결과: (문서 id, 코사인 유사도 0~1). 이미 유사도 내림차순으로 정렬돼 있다.
# d1이 1위지만 2위 d2와의 격차는 크지 않다. d4는 키워드 검색엔 안 나온다.
VECTOR_RESULTS: list[tuple[str, float]] = [
    ("d1", 0.97),
    ("d2", 0.55),
    ("d3", 0.52),
    ("d4", 0.31),
]

# 키워드(BM25류) 검색 결과: (문서 id, 점수 0~20). d2가 압도적 1위다. d5는 벡터 검색엔 안 나온다.
KEYWORD_RESULTS: list[tuple[str, float]] = [
    ("d2", 19.8),
    ("d1", 0.6),
    ("d5", 0.4),
    ("d3", 0.2),
]


def rrf_fuse(
    *ranked_lists: list[tuple[str, float]], k: int = 60
) -> list[tuple[str, float]]:
    """RRF로 여러 순위 리스트를 결합한다. 점수는 무시하고 순위(1위부터)만 쓴다.

    문서 하나가 여러 리스트에 등장하면 1/(k+rank)를 리스트별로 더한다.
    한 리스트에만 있으면 그 리스트의 기여분만 더해진다.
    """
    fused: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, (doc_id, _score) in enumerate(ranked, start=1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda x: x[1], reverse=True)


def _min_max_normalize(ranked: list[tuple[str, float]]) -> dict[str, float]:
    """점수를 0~1로 min-max 정규화한다. 리스트에 없는 문서는 0으로 취급한다."""
    scores = [s for _id, s in ranked]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return {doc_id: 1.0 for doc_id, _s in ranked}
    return {doc_id: (s - lo) / (hi - lo) for doc_id, s in ranked}


def weighted_fuse(
    vector_results: list[tuple[str, float]],
    keyword_results: list[tuple[str, float]],
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
) -> list[tuple[str, float]]:
    """두 리스트를 각각 0~1로 정규화한 뒤 가중치를 곱해 합산한다."""
    vec_norm = _min_max_normalize(vector_results)
    kw_norm = _min_max_normalize(keyword_results)
    doc_ids = set(vec_norm) | set(kw_norm)
    fused = {
        doc_id: vec_norm.get(doc_id, 0.0) * vector_weight
        + kw_norm.get(doc_id, 0.0) * keyword_weight
        for doc_id in doc_ids
    }
    return sorted(fused.items(), key=lambda x: x[1], reverse=True)


def main() -> None:
    logger.info("벡터 검색 결과(코사인 0~1): %s", VECTOR_RESULTS)
    logger.info("키워드 검색 결과(BM25류 0~20): %s", KEYWORD_RESULTS)

    rrf_ranked = rrf_fuse(VECTOR_RESULTS, KEYWORD_RESULTS)
    print("\n[RRF 결합 결과] (순위만 사용, 정규화 불필요)")
    for rank, (doc_id, score) in enumerate(rrf_ranked, start=1):
        print(f"  {rank}. {doc_id}  rrf_score={score:.5f}")

    weighted_ranked = weighted_fuse(VECTOR_RESULTS, KEYWORD_RESULTS)
    print("\n[정규화 후 가중합 결과] (0.5 / 0.5)")
    for rank, (doc_id, score) in enumerate(weighted_ranked, start=1):
        print(f"  {rank}. {doc_id}  weighted_score={score:.5f}")

    rrf_order = [doc_id for doc_id, _ in rrf_ranked]
    weighted_order = [doc_id for doc_id, _ in weighted_ranked]
    if rrf_order != weighted_order:
        print(f"\n두 방식의 순위가 다르다: RRF={rrf_order} vs 가중합={weighted_order}")
    else:
        print(f"\n두 방식의 순위가 같다: {rrf_order}")


if __name__ == "__main__":
    main()
