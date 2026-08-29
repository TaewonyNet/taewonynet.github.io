#!/usr/bin/env python3
"""아무것도 검사하지 않으면서 "통과"를 보고하는 게이트 재현 PoC.

게이트가 초록불이라는 사실은 두 가지 중 하나를 뜻한다.
  (A) 검사했고 문제가 없었다
  (B) 검사 대상이 하나도 없어서 볼 게 없었다

이 둘을 같은 신호로 내보내면 게이트는 아무 말도 하지 않는 것과 같다.
여기서는 흔한 원인 하나(경로 기준 불일치)로 (B)를 만들어 보이고,
검사 건수를 결과에 포함시키는 것만으로 구분되는 것을 확인한다.

독립 실행:
    python3 silent_gate_repro.py
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("silent_gate_repro")

MAX_BYTES = 1024


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True).stdout


def gate_naive(repo: Path, cwd: Path) -> tuple[bool, int]:
    """흔한 실수: 저장소 기준 경로를 현재 디렉터리 기준으로 이어붙인다.

    스테이징 목록은 항상 **저장소 루트 기준**으로 나온다. 하위 디렉터리에서
    돌리면서 그 경로를 cwd 에 붙이면 존재하지 않는 경로가 되고,
    파일이 하나도 안 열려 검사 0건으로 통과한다.
    """
    checked = 0
    for name in _git(repo, "diff", "--cached", "--name-only").splitlines():
        p = cwd / name          # ← 여기가 결함. repo / name 이어야 한다.
        if not p.exists():
            continue            # 조용히 건너뛴다
        checked += 1
        if p.stat().st_size > MAX_BYTES:
            return False, checked
    return True, checked


def gate_fixed(repo: Path, cwd: Path) -> tuple[bool, int]:
    """경로를 저장소 기준으로 맞추고, 검사 0건이면 통과로 보지 않는다."""
    checked = 0
    for name in _git(repo, "diff", "--cached", "--name-only").splitlines():
        p = repo / name
        if not p.exists():
            continue
        checked += 1
        if p.stat().st_size > MAX_BYTES:
            return False, checked
    if checked == 0:
        return False, 0         # 볼 게 없었다 ≠ 문제가 없었다
    return True, checked


def report(label: str, passed: bool, checked: int) -> None:
    verdict = "통과" if passed else "차단"
    note = ""
    if passed and checked == 0:
        note = "  ← 아무것도 검사하지 않고 통과했다"
    logger.info("  %-8s %s (검사 %d건)%s", label, verdict, checked, note)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "-C", str(repo), "init", "-q"], capture_output=True)
        sub = repo / "tools"
        sub.mkdir()

        # 한도를 넘는 파일을 스테이징한다. 게이트는 이걸 막아야 한다.
        (repo / "big.bin").write_text("x" * (MAX_BYTES * 4), encoding="utf-8")
        (repo / "small.txt").write_text("ok\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True)

        logger.info("=== 저장소 루트에서 실행 ===")
        report("허술판", *gate_naive(repo, cwd=repo))
        report("수정판", *gate_fixed(repo, cwd=repo))

        logger.info("=== 하위 디렉터리(tools/)에서 실행 — CI 가 흔히 이렇게 돈다 ===")
        report("허술판", *gate_naive(repo, cwd=sub))
        report("수정판", *gate_fixed(repo, cwd=sub))

        logger.info("두 판의 차이는 검사 로직이 아니라 '검사 건수를 결과에 넣었는가' 하나다.")


if __name__ == "__main__":
    main()
