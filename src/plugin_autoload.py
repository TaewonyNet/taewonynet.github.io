#!/usr/bin/env python3
"""폴더만 추가하면 CLI와 도구 서버에 동시 등록되는 플러그인 로더 PoC.

도구 하나 = 폴더 하나. `tools/<name>/tool.json`(메타)과 `main.py`(실행 파일)만
있으면 로더가 알아서 찾아 등록한다. 로더 코드는 손대지 않는다.

핵심 두 가지:
  1. `tool.json`의 인자 정의로 **런타임에 함수 시그니처를 합성**한다.
     도구 서버(MCP 등)는 introspection으로 파라미터 타입을 읽으므로,
     동적으로 만든 함수에도 `__signature__`를 심어줘야 인식된다.
  2. 실행은 import가 아니라 **subprocess**로 한다. 도구끼리 의존성이
     충돌하지 않고, 폴더마다 독립적으로 테스트할 수 있다.

독립 실행:
    python3 plugin_autoload.py
"""

from __future__ import annotations

import inspect
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("plugin_autoload")

TYPE_MAP: dict[str, type] = {"string": str, "integer": int, "boolean": bool, "number": float}


def load_specs(tools_dir: Path) -> list[dict]:
    """`tools/*/tool.json`을 전부 읽어 사양 목록을 만든다."""
    specs = []
    for meta in sorted(tools_dir.glob("*/tool.json")):
        spec = json.loads(meta.read_text(encoding="utf-8"))
        spec["_dir"] = meta.parent
        specs.append(spec)
    return specs


def build_argv(spec: dict, kwargs: dict) -> list[str]:
    """kwargs를 `--kebab-flag value` 형태의 argv로 바꾼다. 불리언은 플래그만."""
    argv = [sys.executable, str(spec["_dir"] / spec["entry"])]
    for arg in spec["args"]:
        name = arg["name"]
        value = kwargs.get(name)
        if value is None:
            continue
        flag = "--" + name.replace("_", "-")
        if isinstance(value, bool):
            if value:
                argv.append(flag)
        else:
            argv += [flag, str(value)]
    return argv


def make_tool(spec: dict) -> Callable[..., str]:
    """사양 하나로 실행 함수를 합성한다. 시그니처까지 만들어 심는다."""

    def _run(**kwargs: Any) -> str:
        proc = subprocess.run(
            build_argv(spec, kwargs), capture_output=True, text=True, cwd=spec["_dir"]
        )
        if proc.returncode != 0:
            return json.dumps({"ok": False, "error": proc.stderr.strip()}, ensure_ascii=False)
        return proc.stdout.strip()

    params = []
    for arg in spec["args"]:
        annotation = TYPE_MAP.get(arg["type"], str)
        if arg.get("required"):
            params.append(inspect.Parameter(arg["name"], inspect.Parameter.KEYWORD_ONLY,
                                            annotation=annotation))
        else:
            params.append(inspect.Parameter(arg["name"], inspect.Parameter.KEYWORD_ONLY,
                                            annotation=Optional[annotation], default=None))
    _run.__name__ = spec["name"]
    _run.__doc__ = spec["description"]
    _run.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]
    return _run


class FakeToolServer:
    """도구 서버 대역. 실제 MCP 프레임워크도 이런 식으로 시그니처를 읽는다."""

    def __init__(self) -> None:
        self.registry: dict[str, Callable[..., str]] = {}

    def register(self, fn: Callable[..., str]) -> None:
        sig = inspect.signature(fn)
        rendered = ", ".join(
            f"{n}: {inspect.formatannotation(p.annotation)}" for n, p in sig.parameters.items()
        )
        self.registry[fn.__name__] = fn
        logger.info("  등록: %s(%s) — %s", fn.__name__, rendered, fn.__doc__)


# ── 데모용 도구 폴더 생성 ──────────────────────────────────────────────────────
TOOL_FILES: dict[str, tuple[dict, str]] = {
    "greet": (
        {"name": "greet", "description": "이름을 받아 인사한다.", "entry": "main.py",
         "args": [{"name": "name", "type": "string", "required": True},
                  {"name": "loud", "type": "boolean", "required": False}]},
        'import argparse\n'
        'p = argparse.ArgumentParser()\n'
        'p.add_argument("--name", required=True)\n'
        'p.add_argument("--loud", action="store_true")\n'
        'a = p.parse_args()\n'
        'msg = f"안녕하세요, {a.name}님"\n'
        'print(msg.upper() if a.loud else msg)\n',
    ),
    "add": (
        {"name": "add", "description": "두 정수를 더한다.", "entry": "main.py",
         "args": [{"name": "x", "type": "integer", "required": True},
                  {"name": "y", "type": "integer", "required": True}]},
        'import argparse\n'
        'p = argparse.ArgumentParser()\n'
        'p.add_argument("--x", type=int, required=True)\n'
        'p.add_argument("--y", type=int, required=True)\n'
        'a = p.parse_args()\n'
        'print(a.x + a.y)\n',
    ),
    # 로더를 고치지 않고 나중에 추가되는 세 번째 도구
    "upper": (
        {"name": "upper", "description": "문자열을 대문자로 만든다.", "entry": "main.py",
         "args": [{"name": "text", "type": "string", "required": True}]},
        'import argparse\n'
        'p = argparse.ArgumentParser()\n'
        'p.add_argument("--text", required=True)\n'
        'a = p.parse_args()\n'
        'print(a.text.upper())\n',
    ),
}


def write_tool(tools_dir: Path, name: str) -> None:
    spec, code = TOOL_FILES[name]
    d = tools_dir / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "tool.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    (d / "main.py").write_text(code, encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tools_dir = Path(tmp) / "tools"

        logger.info("=== 도구 폴더 2개로 시작 ===")
        for name in ("greet", "add"):
            write_tool(tools_dir, name)
        server = FakeToolServer()
        for spec in load_specs(tools_dir):
            server.register(make_tool(spec))
        logger.info("등록된 도구: %d개", len(server.registry))

        logger.info("=== 실행(각 도구는 별도 프로세스) ===")
        logger.info("  greet(name='태원', loud=True) -> %s",
                    server.registry["greet"](name="태원", loud=True))
        logger.info("  add(x=2, y=40) -> %s", server.registry["add"](x=2, y=40))

        logger.info("=== 폴더 하나를 더 넣는다. 로더 코드는 손대지 않는다 ===")
        write_tool(tools_dir, "upper")
        server2 = FakeToolServer()
        for spec in load_specs(tools_dir):
            server2.register(make_tool(spec))
        logger.info("등록된 도구: %d개 (로더 수정 0줄)", len(server2.registry))
        logger.info("  upper(text='hello') -> %s", server2.registry["upper"](text="hello"))

        logger.info("=== 도구가 실패하면 프로세스 경계에서 격리된다 ===")
        logger.info("  add(x='정수아님', y=1) -> %s", server2.registry["add"](x="정수아님", y=1))


if __name__ == "__main__":
    main()
