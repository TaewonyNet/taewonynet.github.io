"""
LLM 채점 없이 검색 품질 차이가 통계적으로 유의한지 확인하는 최소 PoC.

wilson_interval()은 정확도(성공/전체) 하나에 대한 95% 이항 신뢰구간을 계산한다.
paired_bootstrap_diff()는 같은 골든 케이스에 대해 두 방식(A/B)의 정확도 차이를
paired bootstrap으로 재추정해, 차이의 신뢰구간이 0을 포함하는지(=유의하지 않은지)
확인한다.

독립 실행:
    python3 search_quality_stats.py
"""

from __future__ import annotations

import logging
import math
import random

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("search_quality_stats")


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """성공 successes / 전체 n에 대한 Wilson 95%(z=1.96 기본) 이항 신뢰구간을 반환한다.

    정규근사(단순 +-1.96*sqrt(p(1-p)/n))보다 표본이 작을 때 더 안정적이다.
    """
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = p + z**2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    lower = (center - margin) / denom
    upper = (center + margin) / denom
    return (max(0.0, lower), min(1.0, upper))


def paired_bootstrap_diff(
    results_a: list[int],
    results_b: list[int],
    n_iter: int = 20_000,
    seed: int | None = 0,
) -> tuple[float, tuple[float, float]]:
    """같은 케이스 순서로 짝지어진 두 방식(A/B)의 정확도 차이를 bootstrap으로 추정한다.

    results_a, results_b: 각 케이스에서 정답이면 1, 오답이면 0 (길이가 같아야 함).
    반환: (관측된 차이 A-B, 차이의 95% 신뢰구간)
    """
    if len(results_a) != len(results_b):
        raise ValueError("results_a, results_b는 길이가 같아야 한다(같은 케이스 순서로 짝지어짐)")

    n = len(results_a)
    rng = random.Random(seed)
    observed_diff = sum(results_a) / n - sum(results_b) / n

    diffs = []
    for _ in range(n_iter):
        idx = [rng.randrange(n) for _ in range(n)]
        sample_a = sum(results_a[i] for i in idx) / n
        sample_b = sum(results_b[i] for i in idx) / n
        diffs.append(sample_a - sample_b)

    diffs.sort()
    lower = diffs[int(0.025 * n_iter)]
    upper = diffs[int(0.975 * n_iter)]
    return observed_diff, (lower, upper)


def main() -> None:
    # 골든 케이스 31개를 흉내낸 목 결과: title-only 26/31 정답, RRF결합 24/31 정답.
    n = 31
    title_only_correct = 26
    rrf_correct = 24

    for label, correct in (("title-only", title_only_correct), ("RRF결합", rrf_correct)):
        lo, hi = wilson_interval(correct, n)
        logger.info(
            "%s: %d/%d = %.1f%% [Wilson 95%% CI %.1f%%~%.1f%%]",
            label, correct, n, 100 * correct / n, 100 * lo, 100 * hi,
        )

    results_a = [1] * title_only_correct + [0] * (n - title_only_correct)
    results_b = [1] * rrf_correct + [0] * (n - rrf_correct)
    random.Random(1).shuffle(results_a)
    random.Random(2).shuffle(results_b)

    diff, (lo, hi) = paired_bootstrap_diff(results_a, results_b, n_iter=20_000, seed=0)
    logger.info(
        "차이(A-B)=%.1f%%p, paired bootstrap 95%% CI [%.1f%%p ~ %.1f%%p]",
        100 * diff, 100 * lo, 100 * hi,
    )
    logger.info("신뢰구간이 0을 포함하는가(=차이가 유의하지 않은가): %s", lo <= 0 <= hi)


if __name__ == "__main__":
    main()
