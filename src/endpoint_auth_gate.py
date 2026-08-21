#!/usr/bin/env python3
"""인증 없는 변경 엔드포인트를 AST로 적발하는 PoC.

POST/PUT/DELETE/PATCH 라우트를 훑어 인증 의존성이 걸려 있는지 확인한다.
통과 조건은 셋 중 하나다.

  1. 라우터 전체에 인증이 걸려 있다(blanket guard)
  2. 데코레이터에 인증 의존성이 직접 붙어 있다
  3. 의도적으로 공개한 경로 화이트리스트에 있다

핵심은 1번을 **어떻게 판정하느냐**다. 모듈 이름을 하드코딩하면 나중에
라우터 등록에서 가드를 빼도 계속 통과한다 — 오탐이 아니라 미탐이다.
이 PoC는 두 방식을 나란히 돌려 그 차이를 보여준다.

독립 실행:
    python3 endpoint_auth_gate.py
"""

from __future__ import annotations

import ast
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("endpoint_auth_gate")

MUTATING = {"post", "put", "delete", "patch"}
AUTH_DEP = "require_admin"
PUBLIC_ROUTES = {"/api/v1/collect"}  # 의도적 공개. 리뷰를 거쳐 등록한다.


def _decorator_routes(node: ast.FunctionDef | ast.AsyncFunctionDef):
    """함수에 붙은 변경 라우트 데코레이터를 (메서드, 경로, 데코레이터) 로 내놓는다."""
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call) or not isinstance(dec.func, ast.Attribute):
            continue
        if dec.func.attr not in MUTATING:
            continue
        if not dec.args or not isinstance(dec.args[0], ast.Constant):
            continue
        yield dec.func.attr.upper(), dec.args[0].value, dec


def _has_auth_dependency(dec: ast.Call) -> bool:
    """데코레이터의 dependencies 인자에 인증 의존성이 들어 있는가."""
    for kw in dec.keywords:
        if kw.arg != "dependencies":
            continue
        for sub in ast.walk(kw.value):
            if isinstance(sub, ast.Name) and sub.id == AUTH_DEP:
                return True
    return False


def blanket_guarded_naive(_main_src: str) -> set[str]:
    """첫 판: 가드가 걸린 모듈을 그냥 적어둔다. 미탐의 원인."""
    return {"admin.py"}


def blanket_guarded_derived(main_src: str) -> set[str]:
    """고친 판: 등록 코드에서 역산한다.

    `from .api.v1.admin import router as admin_router` 로 별칭→모듈 맵을 만들고,
    그 별칭이 인증 의존성과 함께 include_router 에 넘겨진 경우만 인정한다.
    """
    tree = ast.parse(main_src)
    alias_to_module: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module.split(".")[-1] + ".py"
            for a in node.names:
                alias_to_module[a.asname or a.name] = module

    guarded: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "include_router" or not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, ast.Name):
            continue
        has_auth = any(
            isinstance(sub, ast.Name) and sub.id == AUTH_DEP
            for kw in node.keywords
            if kw.arg == "dependencies"
            for sub in ast.walk(kw.value)
        )
        if has_auth and first.id in alias_to_module:
            guarded.add(alias_to_module[first.id])
    return guarded


def scan(modules: dict[str, str], main_src: str, blanket_fn) -> list[str]:
    """변경 라우트를 훑어 인증이 없는 것을 찾아낸다."""
    blanket = blanket_fn(main_src)
    findings: list[str] = []
    for filename, src in modules.items():
        tree = ast.parse(src, filename=filename)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for method, path, dec in _decorator_routes(node):
                if filename in blanket or _has_auth_dependency(dec) or path in PUBLIC_ROUTES:
                    continue
                findings.append(f"{filename}:{method} {path}")
    return findings


# ── 데모용 소스 ───────────────────────────────────────────────────────────────
ADMIN = '''
@router.post("/api/v1/agent/targets")
def add_target(body: dict):
    return {}
'''

IDENTITY = '''
@router.post("/api/v1/agent/register", dependencies=[Depends(require_admin)])
def register(body: dict):
    return {}

@router.put("/api/v1/collect")
def collect(body: dict):
    return {}

@router.delete("/api/v1/agent/session")
def drop_session(body: dict):
    return {}
'''

MAIN_GUARDED = '''
from .api.v1.admin import router as admin_router
from .api.v1.identity import router as identity_router

app.include_router(admin_router, dependencies=[Depends(require_admin)])
app.include_router(identity_router)
'''

# 누군가 등록에서 가드를 빼버린 상태
MAIN_UNGUARDED = MAIN_GUARDED.replace(
    "app.include_router(admin_router, dependencies=[Depends(require_admin)])",
    "app.include_router(admin_router)",
)

MODULES = {"admin.py": ADMIN, "identity.py": IDENTITY}


def main() -> None:
    logger.info("=== 정상 상태 — 두 방식 모두 통과해야 한다 ===")
    for label, fn in (("하드코딩", blanket_guarded_naive), ("역산", blanket_guarded_derived)):
        found = scan(MODULES, MAIN_GUARDED, fn)
        logger.info("  %-6s 적발 %d건 %s", label, len(found), found)

    logger.info("=== 등록 코드에서 가드를 제거한 뒤 ===")
    logger.info("  이제 admin.py 의 POST 는 무인증이다. 검사기가 이걸 잡아야 한다.")
    for label, fn in (("하드코딩", blanket_guarded_naive), ("역산", blanket_guarded_derived)):
        found = scan(MODULES, MAIN_UNGUARDED, fn)
        caught = any(f.startswith("admin.py") for f in found)
        verdict = "잡음" if caught else "미탐 — 가드가 사라졌는데 통과시킴"
        logger.info("  %-6s 적발 %d건 %s → %s", label, len(found), found, verdict)

    logger.info("=== 검사기가 무엇을 못 보는가 ===")
    logger.info("  GET 으로 상태를 바꾸는 엔드포인트는 메서드 기준 스캔 밖이다.")
    logger.info("  공개 화이트리스트: %s (리뷰를 거쳐야 등록)", sorted(PUBLIC_ROUTES))


if __name__ == "__main__":
    main()
