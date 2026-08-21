#!/usr/bin/env python3
"""에이전트에게 규칙을 '지시'가 아니라 '게이트'로 강제하는 최소 PoC.

에이전트가 파일을 편집한 직후 훅으로 호출되는 상황을 흉내낸다.
훅은 편집된 파일을 `ast`로 파싱해 함수의 **실제 시그니처**와 **독스트링에 적힌
Args 목록**을 대조하고, 어긋나면 0이 아닌 코드로 종료한다.

지시문("독스트링을 최신으로 유지하세요")은 지켜졌는지 확인할 방법이 없다.
훅은 편집이 일어날 때마다 반드시 실행되므로 놓칠 수가 없다.

독립 실행:
    python3 agent_hook_gate.py
"""

from __future__ import annotations

import ast
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("agent_hook_gate")

ARGS_HEADER = "Args:"


def documented_args(docstring: str | None) -> list[str]:
    """독스트링의 `Args:` 절에 나열된 인자 이름을 뽑는다."""
    if not docstring or ARGS_HEADER not in docstring:
        return []
    tail = docstring.split(ARGS_HEADER, 1)[1]
    names: list[str] = []
    for raw in tail.splitlines():
        line = raw.strip()
        if not line:
            continue
        # 다음 절(Returns: 등)을 만나면 중단
        if line.endswith(":") and " " not in line.rstrip(":"):
            break
        if ":" in line:
            names.append(line.split(":", 1)[0].strip())
    return names


def actual_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """함수 정의에서 실제 인자 이름을 뽑는다(self/cls 제외)."""
    a = node.args
    names = [p.arg for p in (*a.posonlyargs, *a.args, *a.kwonlyargs)]
    if a.vararg:
        names.append(a.vararg.arg)
    if a.kwarg:
        names.append(a.kwarg.arg)
    return [n for n in names if n not in ("self", "cls")]


def check_source(source: str, filename: str = "<edited>") -> list[str]:
    """시그니처와 독스트링이 어긋난 함수를 찾아 위반 목록을 반환한다."""
    violations: list[str] = []
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        documented = documented_args(ast.get_docstring(node))
        if not documented:
            continue  # 문서화 자체를 안 했으면 이 게이트의 대상이 아니다
        real = actual_args(node)
        missing = [n for n in real if n not in documented]
        stale = [n for n in documented if n not in real]
        if missing:
            violations.append(f"{filename}:{node.lineno} {node.name}() 문서에 없는 인자: {missing}")
        if stale:
            violations.append(f"{filename}:{node.lineno} {node.name}() 사라진 인자가 문서에 남음: {stale}")
    return violations


def run_hook(payload: dict) -> int:
    """훅 진입점. PostToolUse 페이로드를 받아 종료 코드를 반환한다.

    Args:
        payload: 편집된 파일 경로(`path`)와 편집 후 내용(`source`)을 담은 딕셔너리.
    """
    path = payload.get("path", "<unknown>")
    source = payload.get("source", "")
    try:
        violations = check_source(source, path)
    except SyntaxError as exc:  # 편집이 파일을 깨뜨린 경우도 게이트가 잡는다
        logger.error("구문 오류로 파싱 실패: %s", exc)
        return 2
    for v in violations:
        logger.error(v)
    return 1 if violations else 0


# ── 데모 ──────────────────────────────────────────────────────────────────────
BEFORE = '''
def fetch(url, timeout):
    """문서를 가져온다.

    Args:
        url: 가져올 주소.
        timeout: 초 단위 제한시간.
    """
    return url, timeout
'''

AFTER = '''
def fetch(url, timeout, retries):
    """문서를 가져온다.

    Args:
        url: 가져올 주소.
        timeout: 초 단위 제한시간.
    """
    return url, timeout, retries
'''


def main() -> None:
    logger.info("=== 편집 전 (문서와 시그니처 일치) ===")
    rc_before = run_hook({"path": "fetcher.py", "source": BEFORE})
    logger.info("훅 종료 코드: %d", rc_before)

    logger.info("=== 에이전트가 인자 하나를 추가하고 문서는 그대로 둔 뒤 ===")
    rc_after = run_hook({"path": "fetcher.py", "source": AFTER})
    logger.info("훅 종료 코드: %d", rc_after)

    logger.info("=== 편집이 파일을 깨뜨린 경우 ===")
    rc_broken = run_hook({"path": "fetcher.py", "source": "def f(:\n    pass\n"})
    logger.info("훅 종료 코드: %d", rc_broken)

    logger.info(
        "지시문이었다면 셋 다 조용히 통과했을 것이다. 게이트는 %d건을 막았다.",
        sum(1 for rc in (rc_before, rc_after, rc_broken) if rc != 0),
    )


if __name__ == "__main__":
    if not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            sys.exit(run_hook(json.loads(raw)))
    main()
