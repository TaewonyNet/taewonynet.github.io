#!/usr/bin/env python3
"""워킹트리와 git 히스토리에서 비밀·내부 표식을 찾아내는 감사 PoC.

공개 전에 "전수 확인했다"고 말하려면 무엇을 훑었는지가 코드에 남아야 한다.
사람이 눈으로 보는 확인은 범위가 사람 판단에 갇히고, 그 범위 밖은 조용히 빠진다.

설계에서 중요한 네 가지:
  1. 워킹트리는 `git ls-files` 로만 훑는다 — 빌드 산출물·무시된 파일이 저절로 빠진다.
     대신 **아직 추적되지 않은 새 파일은 안 보인다**(마지막 데모 참고).
  2. 히스토리는 추가된 줄(`+`)만, 그리고 시크릿 패턴만 본다. 전 카테고리를 히스토리까지
     돌리면 느려서 아무도 안 돌린다.
  3. 리포트가 곧 2차 유출이 되지 않도록 적중값을 마스킹한다.
  4. 종료 코드로 말한다(0 깨끗 / 1 발견 / 2 설정오류). 사람·CI·에이전트가 같은 신호를 쓴다.

독립 실행:
    python3 secret_leak_audit.py
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("secret_leak_audit")

# 카테고리별 패턴. 시크릿만이 아니라 **내부 표식**까지 넣는 게 요점이다.
PATTERNS: dict[str, list[str]] = {
    "secret": [r"AKIA[0-9A-Z]{16}", r"ghp_[A-Za-z0-9]{20,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"],
    "private_ip": [r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", r"\b192\.168\.\d{1,3}\.\d{1,3}\b"],
    # 시크릿 스캐너가 절대 못 잡는 것 — 사내에서만 뜻이 통하는 라벨
    "dev_label": [r"\bD-\d{1,3}\b", r"\bGT-?\d{1,3}\b", r"\bIMPL_\d{1,3}\b"],
}
# 추적되면 안 되는 것들. 대형 유출 직전 신호다.
EXPORT_DENY = ("*.db", "*.sqlite", ".env", "mcp.json")
IGNORE_MARK = "audit:ignore"


def mask(cat: str, s: str) -> str:
    """시크릿만 가린다. 리포트 자체가 2차 유출이 되면 안 되기 때문이다.

    반대로 내부 라벨·IP까지 가리면 무엇을 고쳐야 할지 알 수 없는 리포트가 된다.
    가리는 목적은 '보안'이지 '일관성'이 아니다.
    """
    return (s[:4] + "…") if cat == "secret" else s


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True).stdout


def scan_worktree(repo: Path) -> list[tuple[str, int, str, str]]:
    """추적 중인 파일만 훑는다."""
    out = []
    for name in git(repo, "ls-files").splitlines():
        p = repo / name
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue  # 바이너리·심링크는 건너뛴다
        for i, line in enumerate(text.splitlines(), 1):
            if IGNORE_MARK in line:
                continue
            for cat, pats in PATTERNS.items():
                for pat in pats:
                    for m in re.finditer(pat, line):
                        out.append((name, i, cat, mask(cat, m.group(0))))
    return out


def scan_history(repo: Path) -> list[tuple[str, str]]:
    """추가된 줄에서 시크릿만 본다. 전 카테고리를 돌리면 느려서 아무도 안 쓴다."""
    out = []
    diff = git(repo, "log", "--all", "-p", "--no-color")
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for pat in PATTERNS["secret"]:
            for m in re.finditer(pat, line):
                out.append(("secret", mask("secret", m.group(0))))
    return out


def check_export_guard(repo: Path) -> list[str]:
    """추적되면 안 되는 파일이 추적 중인지 본다."""
    tracked = git(repo, "ls-files").splitlines()
    hits = []
    for name in tracked:
        n = Path(name).name
        for pat in EXPORT_DENY:
            if (pat.startswith("*") and n.endswith(pat[1:])) or n == pat:
                hits.append(name)
    return hits


def audit(repo: Path) -> int:
    wt = scan_worktree(repo)
    hist = scan_history(repo)
    exp = check_export_guard(repo)
    for name, line, cat, val in wt:
        logger.info("  [워킹트리] %s:%d  %s  %s", name, line, cat, val)
    for cat, val in hist:
        logger.info("  [히스토리] %s  %s  (커밋에서 지워도 남아 있다)", cat, val)
    for name in exp:
        logger.info("  [반출가드] %s 가 추적 중이다", name)
    return 1 if (wt or hist or exp) else 0


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _run(repo, "init", "-q")
        _run(repo, "config", "user.email", "t@example.com")
        _run(repo, "config", "user.name", "t")

        # 1) 시크릿을 커밋했다가 지운다 — 워킹트리는 깨끗해지지만 히스토리엔 남는다
        (repo / "config.py").write_text('TOKEN = "ghp_EXAMPLEFAKETOKENNOTREAL0001"\n', encoding="utf-8")
        _run(repo, "add", "-A"); _run(repo, "commit", "-qm", "add")
        (repo / "config.py").write_text('TOKEN = os.environ["TOKEN"]\n', encoding="utf-8")
        _run(repo, "add", "-A"); _run(repo, "commit", "-qm", "remove")

        # 2) 내부 개발 라벨 — 시크릿 스캐너는 절대 못 잡는다
        (repo / "notes.md").write_text("D-27 결정으로 GT15 를 폐기했다.\n", encoding="utf-8")
        # 3) 반출되면 안 되는 파일이 추적된다
        (repo / "local.db").write_text("x", encoding="utf-8")
        # 4) 오탐을 잠재우는 방법
        (repo / "doc.md").write_text("예시 IP 10.0.0.1 은 문서용이다  # audit:ignore\n", encoding="utf-8")
        _run(repo, "add", "-A"); _run(repo, "commit", "-qm", "more")

        logger.info("=== 감사 실행 ===")
        rc = audit(repo)
        logger.info("종료 코드: %d", rc)

        logger.info("=== 추적되지 않은 파일은 보이지 않는다 ===")
        (repo / "draft.md").write_text("D-99 미추적 파일의 내부 라벨\n", encoding="utf-8")
        logger.info("  새 파일 생성 후 재실행 → 적발 %d건", len(scan_worktree(repo)))
        _run(repo, "add", "-A")
        logger.info("  git add 후 재실행       → 적발 %d건", len(scan_worktree(repo)))
        logger.info("  스캔 범위가 '추적 중'이라, 새 파일은 스테이징 전엔 감사 대상이 아니다.")


if __name__ == "__main__":
    main()
