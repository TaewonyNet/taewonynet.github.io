"""cross-encoder 리랭킹을 onnx 경로로 흉내내고, 측정 조건(콜드로드/입력 길이)이 지연시간을 어떻게 왜곡하는지 보여주는 벤치마크.

여기서 쓰는 400ms/5ms는 실제 측정치가 아니라 "느린 조건 vs 빠른 조건"의 차이를
과장해서 보여주기 위한 임의의 예시 값이다. 글에 인용된 실측치(12.5초, 2463ms,
565ms 등)는 실제 시스템에서 별도로 측정된 값으로, 이 데모가 재현하는 숫자가
아니다.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

try:
    import fastembed  # type: ignore # noqa: F401

    HAS_FASTEMBED = True
    logger.info("fastembed(onnxruntime 기반) 설치 확인됨 — 실제 환경에서는 이 경로로 추론한다")
except ImportError:
    HAS_FASTEMBED = False
    logger.info("fastembed 미설치 — 목(mock) 스코어링으로 대체한다(구조는 동일)")

# 이 PoC는 fastembed 설치 여부와 무관하게 목 스코어링으로 고정한다.
# 실제 onnx 모델을 매번 내려받으면 벤치마크 결과가 네트워크 상태에 좌우돼
# "측정 조건이 결과를 왜곡한다"는 핵심 논지를 재현성 있게 보여줄 수 없기 때문이다.
# 실제 교체 지점은 rerank() 안의 아래 분기 하나 뿐이다.


def _mock_score(query: str, candidate: str, simulate_ms: float) -> float:
    """실제 onnx 추론 대신, 겹치는 어절 수 기반 목 점수 + 지연 흉내를 낸다."""
    time.sleep(simulate_ms / 1000.0)
    q_words = set(query.split())
    c_words = set(candidate.split())
    overlap = len(q_words & c_words)
    return overlap / (len(q_words) + 1e-6)


def rerank(
    query: str, candidates: list[str], simulate_ms_per_item: float = 0.0
) -> list[tuple[str, float]]:
    """후보 문서 리스트를 질문과의 관련성 점수로 재정렬한다.

    실제 환경 교체 지점: fastembed.rerank.cross_encoder.TextCrossEncoder 등
    onnxruntime 기반 cross-encoder로 아래 분기만 바꿔 끼우면 된다.
    """
    scores = [_mock_score(query, c, simulate_ms_per_item) for c in candidates]
    ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
    return ranked


def bench_condition(
    label: str, query: str, candidates: list[str], simulate_ms_per_item: float
) -> float:
    """측정 조건 하나(콜드로드/입력 길이/스레드 등을 흉내낸 지연)로 리랭킹 시간을 잰다."""
    start = time.perf_counter()
    rerank(query, candidates, simulate_ms_per_item=simulate_ms_per_item)
    elapsed_ms = (time.perf_counter() - start) * 1000
    print(f"[{label}] {elapsed_ms:.1f}ms  ({len(candidates)}개 후보)")
    return elapsed_ms


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    query = "검색 리랭킹 지연시간 줄이기"
    candidates = [
        "검색 결과 리랭킹으로 관련성을 높이는 방법",
        "오늘 점심 메뉴 추천",
        "리랭킹 지연시간을 onnx로 줄이는 벤치마크",
        "날씨가 맑다",
    ]

    print("측정 조건에 따라 같은 리랭킹 로직의 체감 지연이 얼마나 달라지는지 비교한다.\n")

    # 콜드로드+fp32+긴 입력을 흉내낸 조건 — 과거 "리랭킹은 못 쓴다"는 결론이 나온 조건
    bench_condition("콜드로드+fp32 흉내(느린 조건)", query, candidates, simulate_ms_per_item=400.0)

    # 워밍업 후 onnx+int8+짧은 입력을 흉내낸 조건
    bench_condition("워밍업+onnx int8 흉내(빠른 조건)", query, candidates, simulate_ms_per_item=5.0)

    print("\n최종 재정렬 결과 (빠른 조건 기준):")
    for text, score in rerank(query, candidates, simulate_ms_per_item=5.0):
        print(f"  {score:.3f}  {text}")
