"""공급자별 CircuitBreaker + 우선순위 리스트 기반 자동 폴백.

연속 실패가 threshold를 넘으면 OPEN으로 전환해 요청 자체를 건너뛰고,
recovery_timeout 후 HALF_OPEN에서 프로브 1건만 통과시켜 복구 여부를 확인한다.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """provider 1개에 대응하는 CLOSED/OPEN/HALF_OPEN 상태 머신."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"

    def is_available(self, now: float | None = None) -> bool:
        """요청을 보내도 되는지 판단한다. OPEN -> HALF_OPEN 전이도 여기서 처리한다."""
        now = time.time() if now is None else now
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if now - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("circuit -> HALF_OPEN (probe 허용)")
                return True
            return False
        # HALF_OPEN: 프로브 1건만 허용한다는 전제로, 호출 측이 결과를 바로 report한다고 가정.
        return True

    def report_success(self) -> None:
        if self.state != "CLOSED":
            logger.info("circuit -> CLOSED (복구 확인)")
        self.state = "CLOSED"
        self.failure_count = 0

    def report_failure(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self.last_failure_time = now
        if self.state == "HALF_OPEN":
            self.state = "OPEN"
            logger.warning("circuit HALF_OPEN 프로브 실패 -> OPEN 재개방")
            return
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning("circuit -> OPEN (연속 실패 %d회)", self.failure_count)


def call_with_fallback(
    providers_in_priority: list[str],
    breakers: dict[str, CircuitBreaker],
    call_fn: Callable[[str], str],
) -> tuple[str, str]:
    """우선순위대로 provider를 순회하며 열려있지 않은 곳으로 재시도한다.

    반환값: (성공한 provider 이름, 응답 텍스트). 전부 실패/OPEN이면 예외를 낸다.
    """
    last_error: Exception | None = None
    for name in providers_in_priority:
        breaker = breakers[name]
        if not breaker.is_available():
            logger.info("skip provider=%s (circuit OPEN)", name)
            continue
        try:
            result = call_fn(name)
        except Exception as e:  # noqa: BLE001 - 공급자 예외를 서킷 상태로 흡수
            breaker.report_failure()
            last_error = e
            logger.warning("provider=%s failed: %s", name, e)
            continue
        breaker.report_success()
        return name, result
    raise RuntimeError(f"all providers unavailable, last_error={last_error}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    priority = ["gemini", "groq", "cerebras"]
    breakers = {name: CircuitBreaker(failure_threshold=3, recovery_timeout=5) for name in priority}

    # gemini는 항상 실패, groq는 성공한다고 가정한 더미 호출 함수.
    def flaky_call(name: str) -> str:
        if name == "gemini":
            raise ConnectionError("gemini 503")
        return f"{name} 응답 성공"

    # 연속 3회 실패시키면 gemini 서킷이 OPEN으로 전환된다.
    for i in range(3):
        provider, text = call_with_fallback(priority, breakers, flaky_call)
        print(f"round {i}: used={provider}, resp={text}, gemini_state={breakers['gemini'].state}")

    print("gemini breaker state after 3 rounds:", breakers["gemini"].state)

    # OPEN 상태에서는 gemini를 건너뛰고 바로 groq으로 간다(빠른 실패).
    provider, text = call_with_fallback(priority, breakers, flaky_call)
    print(f"post-open round: used={provider}, resp={text}")

    # recovery_timeout 경과 후 HALF_OPEN 프로브가 성공하면 CLOSED로 복귀한다.
    def now_recovered(name: str) -> str:
        return f"{name} 복구됨"

    future_breaker = breakers["gemini"]
    assert future_breaker.is_available(now=time.time() + 6) is True  # HALF_OPEN 전이 확인
    future_breaker.report_success()
    print("gemini breaker state after recovery probe:", future_breaker.state)
