#!/usr/bin/env python3
"""에이전트 제어 레이어를 기본 거부(deny-by-default)로 설계한 최소 PoC.

에이전트가 외부 대상에 동작을 걸 때 통과해야 하는 관문을 모았다.

  1. 허용목록이 비어 있으면 **전부 거부**한다. 추가는 명시적 옵트인이다.
  2. connect -> action -> disconnect 수명주기를 강제한다. 연결 없이 동작 불가.
  3. 동시 연결 수, 동작 간 최소 간격, 연결 유효시간(TTL)을 정책 상수로 고정한다.
  4. 동작 종류 자체를 화이트리스트로 제한한다(임의 스크립트 실행 차단).

정책을 상수 한 곳에 모으는 이유는, 나중에 누가 우회 경로를 만들었을 때
정적 검사로 잡아내기 위해서다(마지막 데모 참고).

독립 실행:
    python3 agent_control_policy.py
"""

from __future__ import annotations

import ast
import inspect
import logging
import sys
import threading
import time

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("agent_control_policy")

# ── 정책 (단일 원본) ──────────────────────────────────────────────────────────
HOST_ALLOWLIST: frozenset[str] = frozenset()  # 비어 있으면 전면 거부
MAX_CONCURRENT: int = 3
ACTION_MIN_INTERVAL_S: float = 1.5
OP_TTL_S: int = 900
ALLOWED_ACTIONS: frozenset[str] = frozenset({"click", "scroll", "read"})


class Denied(Exception):
    """정책 위반. 큐에 명령이 실리기 전에 던진다."""


def host_allowed(host: str) -> bool:
    """허용목록 조회. 테스트에서 목록을 갈아끼울 수 있도록 모듈을 다시 참조한다.

    `import <모듈명>`으로 자기 자신을 참조하면 안 된다 — 스크립트로 직접 실행할 때
    `__main__`과 별개의 모듈 객체가 하나 더 생겨서, 한쪽에서 바꾼 허용목록이
    다른 쪽에 반영되지 않는다. `sys.modules[__name__]`은 항상 자기 자신이다.
    """
    return host in sys.modules[__name__].HOST_ALLOWLIST


class Holder:
    """op별 연결 상태. 동시성·간격·만료를 한 자리에서 강제한다."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: dict[str, dict[str, float]] = {}

    def connect(self, op: str, now: float) -> None:
        with self._lock:
            if len(self._active) >= MAX_CONCURRENT:
                raise Denied(f"동시 연결 한도 초과({MAX_CONCURRENT})")
            self._active[op] = {"connected_at": now, "last_action_at": 0.0}

    def gate(self, op: str, now: float) -> None:
        with self._lock:
            state = self._active.get(op)
            if state is None:
                raise Denied("연결되지 않은 op")
            if now - state["connected_at"] > OP_TTL_S:
                del self._active[op]
                raise Denied(f"연결 만료(TTL {OP_TTL_S}s)")
            if now - state["last_action_at"] < ACTION_MIN_INTERVAL_S:
                raise Denied(f"동작 간격 미달({ACTION_MIN_INTERVAL_S}s)")
            state["last_action_at"] = now

    def disconnect(self, op: str) -> None:
        with self._lock:
            self._active.pop(op, None)

    @property
    def count(self) -> int:
        return len(self._active)


HOLDER = Holder()
QUEUE: list[tuple[str, str]] = []  # 실제로 발행된 명령. 거부되면 비어 있어야 한다.


def run_recipe(op: str, host: str, action: str, now: float | None = None) -> None:
    """대상에 동작 하나를 건다. 관문을 통과해야만 큐에 실린다."""
    now = time.monotonic() if now is None else now
    if not host_allowed(host):
        raise Denied(f"허용목록에 없는 host: {host!r}")
    if action not in ALLOWED_ACTIONS:
        raise Denied(f"허용되지 않은 동작: {action!r}")
    HOLDER.gate(op, now)
    QUEUE.append((op, action))


def _try(label: str, fn) -> None:
    try:
        fn()
        logger.info("  통과   %s", label)
    except Denied as exc:
        logger.info("  거부   %s — %s", label, exc)


# ── 정책 우회 경로를 정적으로 잡는 게이트 ────────────────────────────────────
def check_allowlist_referenced(func) -> bool:
    """`run_recipe` 본문이 허용목록을 실제로 참조하는지 AST로 확인한다.

    나중에 누군가 조건문을 지워도 테스트는 초록불일 수 있다. 이 검사는
    '가드가 코드에 남아 있는가'를 따로 본다.
    """
    tree = ast.parse(inspect.getsource(func))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    return "host_allowed" in names or "HOST_ALLOWLIST" in names


def main() -> None:
    global HOST_ALLOWLIST

    logger.info("=== 1) 허용목록이 비어 있으면 전면 거부 ===")
    HOLDER.connect("op1", now=0.0)
    _try("run_recipe(host='example.com')", lambda: run_recipe("op1", "example.com", "click", 10.0))
    logger.info("  큐에 실린 명령: %d건 (0이어야 한다)", len(QUEUE))

    logger.info("=== 2) 명시적으로 추가한 host만 통과 ===")
    HOST_ALLOWLIST = frozenset({"example.com"})
    _try("run_recipe(host='example.com')", lambda: run_recipe("op1", "example.com", "click", 10.0))
    _try("run_recipe(host='other.com')", lambda: run_recipe("op1", "other.com", "click", 20.0))
    logger.info("  큐에 실린 명령: %d건", len(QUEUE))

    logger.info("=== 3) 동작 간격 미달은 거부 ===")
    _try("0.5초 뒤 재시도", lambda: run_recipe("op1", "example.com", "click", 10.5))
    _try("2.0초 뒤 재시도", lambda: run_recipe("op1", "example.com", "click", 12.0))

    logger.info("=== 4) 허용되지 않은 동작 ===")
    _try("action='script'", lambda: run_recipe("op1", "example.com", "script", 20.0))

    logger.info("=== 5) 동시 연결 한도 ===")
    for i in range(2, 5):
        _try(f"connect(op{i})", lambda i=i: HOLDER.connect(f"op{i}", now=0.0))
    logger.info("  현재 연결 수: %d (한도 %d)", HOLDER.count, MAX_CONCURRENT)

    logger.info("=== 6) TTL 만료 ===")
    _try("TTL 초과 후 동작", lambda: run_recipe("op1", "example.com", "click", OP_TTL_S + 100))

    logger.info("=== 7) 가드가 코드에서 사라졌는지 정적 확인 ===")
    logger.info("  run_recipe가 허용목록을 참조하는가: %s", check_allowlist_referenced(run_recipe))

    logger.info("최종 큐: %s", QUEUE)


if __name__ == "__main__":
    main()
