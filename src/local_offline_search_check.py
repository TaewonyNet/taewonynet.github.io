"""
로컬·오프라인 검색이 실제로 네트워크를 타지 않는지 확인하는 최소 PoC.

1) 현재 프로세스 메모리 사용량을 psutil(있으면) 또는 resource(표준 라이브러리)로 측정한다.
2) socket.socket을 몽키패치해 검색 도중 소켓이 열리면 예외를 던지게 만들고,
   in-memory 인덱스만으로 질의에 답하는 함수가 실제로 "네트워크를 열지 않는다"를 증명한다.

독립 실행:
    python3 local_offline_search_check.py
"""

from __future__ import annotations

import logging
import socket
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("local_offline_search_check")

try:
    import psutil  # type: ignore

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    import resource


def current_memory_mb() -> float:
    """현재 프로세스 메모리 사용량(MB)을 반환한다. psutil 없으면 resource로 근사한다."""
    if HAS_PSUTIL:
        proc = psutil.Process()
        return proc.memory_info().rss / (1024 * 1024)
    # resource.ru_maxrss 단위는 리눅스에서 KB, macOS에서 byte라 플랫폼별 편차가 있다.
    # 여기서는 리눅스(KB) 기준으로 가정한다.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


class NetworkOpenedError(RuntimeError):
    """검색 중 소켓이 열리면 던지는 예외 — '오프라인 동작'을 강제로 검증하기 위함."""


@contextmanager
def forbid_network():
    """블록 안에서 socket.socket()이 호출되면 즉시 실패시킨다."""

    original = socket.socket

    def _blocked(*args, **kwargs):
        raise NetworkOpenedError("검색 도중 네트워크 소켓이 열렸다 — 오프라인 요건 위반")

    socket.socket = _blocked  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original  # type: ignore[assignment]


class LocalIndex:
    """수집(acquire) 단계에서 이미 로컬에 내려받은 문서만 다루는 인메모리 인덱스.

    실제 구현은 ONNX 임베딩 모델로 벡터를 계산하지만, 여기서는 네트워크 의존성이
    없다는 구조만 보이면 되므로 부분 문자열 매칭으로 대체한다.
    """

    def __init__(self, documents: list[str]) -> None:
        self._documents = documents

    def query(self, text: str) -> list[str]:
        return [d for d in self._documents if text.lower() in d.lower()]


def main() -> None:
    mem_before = current_memory_mb()
    logger.info("메모리 사용량(측정 도구=%s): %.1f MB", "psutil" if HAS_PSUTIL else "resource", mem_before)

    index = LocalIndex(
        [
            "검색 인프라 설계 노트: 로컬 임베딩 모델 사용",
            "리랭커는 ONNX로 한 번만 내려받아 이후 오프라인 동작",
            "수집 단계만 네트워크 필요, 이후는 완전 로컬",
        ]
    )

    try:
        with forbid_network():
            results = index.query("오프라인")
        logger.info("네트워크 차단 상태에서 질의 성공: %d건 매칭", len(results))
        for r in results:
            logger.info("  - %s", r)
    except NetworkOpenedError as exc:
        logger.error("검증 실패: %s", exc)
        raise

    mem_after = current_memory_mb()
    logger.info("측정 종료 시 메모리 사용량: %.1f MB (변화 %.1f MB)", mem_after, mem_after - mem_before)
    logger.info("16GB(%d MB) 이내 여부: %s", 16 * 1024, mem_after < 16 * 1024)


if __name__ == "__main__":
    main()
