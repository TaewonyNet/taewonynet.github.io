"""
여러 DB를 federation한 검색에서 리랭킹 후보 풀을 DB 수만큼 나눠 분산하는 최소 PoC.

DB가 늘어날수록 "각 DB에서 넉넉히 가져와 전부 리랭킹"하면 후보 수가 DB 수에 비례해
불어난다. distribute_pool()은 전체 리랭킹 풀(RERANK_POOL)을 DB 수로 나눠 DB당 몫을
계산하되, k+offset(정렬에 최소로 필요한 개수)은 항상 보장한다.

독립 실행:
    python3 rerank_pool_distribute.py
"""

from __future__ import annotations

import logging
import random
import time

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("rerank_pool_distribute")

RERANK_POOL = 60  # 전체 리랭킹 후보 풀 상한 (분산 후 기준)


def distribute_pool(total_pool: int, n_dbs: int, k: int, offset: int) -> int:
    """전체 리랭킹 풀을 DB 수로 나눠 DB당 가져올 후보 수를 계산한다.

    최소 k + offset은 항상 보장한다 — 그 이하로 가져오면 원하는 순위(offset)까지
    페이지네이션할 재료 자체가 없어지기 때문이다.
    """
    if n_dbs <= 0:
        raise ValueError("n_dbs는 1 이상이어야 한다")
    per_db = total_pool // n_dbs
    return max(per_db, k + offset)


class MockRepository:
    """실제 DB 대신 지연시간과 후보 개수를 흉내내는 목(mock) 저장소."""

    def __init__(self, name: str, size: int, latency_per_candidate: float) -> None:
        self.name = name
        self.size = size
        self.latency_per_candidate = latency_per_candidate

    def fetch_candidates(self, n: int) -> list[str]:
        n = min(n, self.size)
        time.sleep(self.latency_per_candidate * n)
        return [f"{self.name}-doc-{i}" for i in range(n)]


def run_federated_search(repos: list[MockRepository], per_db_pool: int) -> tuple[list[str], float]:
    start = time.perf_counter()
    candidates: list[str] = []
    for repo in repos:
        candidates.extend(repo.fetch_candidates(per_db_pool))
    elapsed = time.perf_counter() - start
    return candidates, elapsed


def main() -> None:
    # 실측 규모를 근사한 목 데이터: 문서 저장소·코드 저장소·이슈트래커 3개 federation.
    repos = [
        MockRepository("docs", size=28_963, latency_per_candidate=0.02),
        MockRepository("code", size=3_527, latency_per_candidate=0.02),
        MockRepository("issues", size=146, latency_per_candidate=0.02),
    ]
    n_dbs = len(repos)
    k, offset = 10, 0

    # 분배 전: DB마다 고정 60개씩 넉넉히 가져오는 방식.
    before_per_db = 60
    before_candidates, before_elapsed = run_federated_search(repos, before_per_db)
    logger.info(
        "분배 전: DB당 %d개 x %dDB = 총 후보 %d개, %.2f초",
        before_per_db, n_dbs, len(before_candidates), before_elapsed,
    )

    # 분배 후: distribute_pool()로 DB당 몫을 계산.
    after_per_db = distribute_pool(RERANK_POOL, n_dbs, k, offset)
    after_candidates, after_elapsed = run_federated_search(repos, after_per_db)
    logger.info(
        "분배 후: DB당 %d개 x %dDB = 총 후보 %d개, %.2f초",
        after_per_db, n_dbs, len(after_candidates), after_elapsed,
    )

    random.seed(0)  # 데모 재현성 (실제 리랭킹 스코어링을 흉내내지는 않음)


if __name__ == "__main__":
    main()
