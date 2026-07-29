"""라운드로빈 키 로테이션 + 실패 쿨다운으로 무료 API 키 풀을 관리하는 KeyManager.

`mark_failed(key)`가 호출되면 해당 키를 N초 쿨다운시켜 다음 라운드에서 건너뛴다.
쿨다운이 끝나면 자동으로 풀에 복귀한다.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class _KeyState:
    key: str
    cooldown_until: float = 0.0

    def is_cooling_down(self, now: float) -> bool:
        return now < self.cooldown_until


class NoAvailableKeyError(RuntimeError):
    """풀의 모든 키가 쿨다운 중일 때 발생한다."""


@dataclass
class KeyManager:
    keys: list[str]
    cooldown_seconds: float = 300.0
    _states: dict[str, _KeyState] = field(init=False, default_factory=dict)
    _cursor: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if not self.keys:
            raise ValueError("keys must not be empty")
        self._states = {k: _KeyState(key=k) for k in self.keys}

    def get_next_key(self, now: float | None = None) -> str:
        """라운드로빈으로 다음 활성 키를 반환한다. 전부 쿨다운 중이면 예외를 낸다."""
        now = time.time() if now is None else now
        n = len(self.keys)
        for offset in range(n):
            idx = (self._cursor + offset) % n
            candidate = self.keys[idx]
            if not self._states[candidate].is_cooling_down(now):
                self._cursor = (idx + 1) % n
                return candidate
        raise NoAvailableKeyError("all keys are cooling down")

    def mark_failed(self, key: str, now: float | None = None) -> None:
        """키를 실패 처리하고 cooldown_seconds 동안 선택 대상에서 제외한다."""
        now = time.time() if now is None else now
        state = self._states.setdefault(key, _KeyState(key=key))
        state.cooldown_until = now + self.cooldown_seconds
        logger.warning("key=%s marked failed, cooldown until %.0f", key[:8], state.cooldown_until)

    def active_count(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        return sum(1 for s in self._states.values() if not s.is_cooling_down(now))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    manager = KeyManager(keys=["key-A", "key-B", "key-C"], cooldown_seconds=5)

    # 정상 라운드로빈: A -> B -> C -> A ...
    for _ in range(5):
        print("selected:", manager.get_next_key())

    # key-B가 429를 받았다고 가정하고 쿨다운시킨다.
    manager.mark_failed("key-B")
    print("active count after 1 failure:", manager.active_count())

    # 쿨다운 중인 key-B는 다음 라운드에서 건너뛴다.
    for _ in range(4):
        print("selected (B cooling down):", manager.get_next_key())

    # 쿨다운 시간이 지나면 자동 복귀한다.
    future = time.time() + 6
    print("selected (after cooldown expires):", manager.get_next_key(now=future))
