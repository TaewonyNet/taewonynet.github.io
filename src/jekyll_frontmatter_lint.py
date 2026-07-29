#!/usr/bin/env python3
"""Jekyll(Chirpy) frontmatter의 tags/categories 안 따옴표 없는 순수 숫자 항목을 찾아낸다.

`tags: [2026, 1]`처럼 숫자 태그가 따옴표 없이 들어가면 YAML 파서가 정수로
읽어버려 Chirpy의 태그 페이지 생성 로직(문자열 전제)이 어긋난다. 이 스크립트는
frontmatter 텍스트를 정규식으로 스캔해 `tags:`/`categories:` 리스트 안의
따옴표 없는 순수 숫자 항목을 경고하고, `--fix`를 주면 자동으로 따옴표를 씌운다.

YAML 라이브러리로 파싱하면 "따옴표가 있었는지" 정보 자체가 사라지므로
(파싱 시점엔 이미 str/int로 확정) 원본 텍스트 라인 단위로 검사한다.

requirements: 표준 라이브러리만 사용 (pyyaml 불필요)
"""
from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# tags: [회고, 2026, 1]  /  categories: [Quick, Development]
LIST_FIELD_RE = re.compile(r"^(?P<key>tags|categories):\s*\[(?P<items>[^\]]*)\]\s*$")
BARE_NUMBER_RE = re.compile(r"^\d+$")


def split_items(raw: str) -> list[str]:
    """`[회고, 2026, '1']` 안의 항목을 콤마 기준으로 분리한다 (따옴표 보존)."""
    return [item.strip() for item in raw.split(",") if item.strip()]


def find_bare_numeric_tags(frontmatter_text: str) -> list[tuple[int, str, list[str]]]:
    """frontmatter 텍스트에서 따옴표 없는 순수 숫자 항목이 있는 라인을 찾는다.

    반환: (라인번호, 필드명, 따옴표 없는 숫자 항목 리스트)
    """
    findings = []
    for lineno, line in enumerate(frontmatter_text.splitlines(), start=1):
        m = LIST_FIELD_RE.match(line)
        if not m:
            continue
        bare = [item for item in split_items(m.group("items")) if BARE_NUMBER_RE.match(item)]
        if bare:
            findings.append((lineno, m.group("key"), bare))
    return findings


def fix_bare_numeric_tags(frontmatter_text: str) -> str:
    """따옴표 없는 순수 숫자 항목을 `'항목'` 형태로 감싼 텍스트를 반환한다."""
    fixed_lines = []
    for line in frontmatter_text.splitlines():
        m = LIST_FIELD_RE.match(line)
        if not m:
            fixed_lines.append(line)
            continue
        items = split_items(m.group("items"))
        quoted = [f"'{item}'" if BARE_NUMBER_RE.match(item) else item for item in items]
        fixed_lines.append(f"{m.group('key')}: [{', '.join(quoted)}]")
    return "\n".join(fixed_lines)


def load_frontmatter(path: Path) -> tuple[str, str, str] | None:
    """`(전체텍스트, frontmatter, 나머지본문)`. frontmatter가 없으면 None."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return text, parts[1], parts[2]


def lint_file(path: Path, fix: bool = False) -> bool:
    """파일 1개를 검사한다. 문제가 없으면 True."""
    loaded = load_frontmatter(path)
    if loaded is None:
        logger.debug("frontmatter 없음, 건너뜀: %s", path)
        return True

    _, fm, body = loaded
    findings = find_bare_numeric_tags(fm)
    if not findings:
        return True

    for lineno, key, bare in findings:
        logger.warning("%s:%d — %s 안 따옴표 없는 숫자 항목: %s", path, lineno, key, bare)

    if fix:
        fixed_fm = fix_bare_numeric_tags(fm)
        path.write_text(f"---{fixed_fm}---{body}", encoding="utf-8")
        logger.info("고침 완료: %s", path)

    return False


def lint_paths(paths: list[Path], fix: bool = False) -> int:
    """여러 파일/디렉터리를 검사하고 문제 있던 파일 수를 반환한다."""
    md_files: list[Path] = []
    for p in paths:
        if p.is_dir():
            md_files.extend(sorted(p.rglob("*.md")))
        else:
            md_files.append(p)

    bad_count = 0
    for md in md_files:
        if not lint_file(md, fix=fix):
            bad_count += 1
    return bad_count


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="검사할 .md 파일 또는 디렉터리")
    parser.add_argument("--fix", action="store_true", help="따옴표를 자동으로 씌워 파일을 고친다")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    bad_count = lint_paths(args.paths, fix=args.fix)
    if bad_count:
        logger.warning("문제 있는 파일: %d개 (--fix로 자동 수정 가능)", bad_count)
    else:
        logger.info("모든 파일 정상")
    return 1 if (bad_count and not args.fix) else 0


def _demo() -> None:
    """CLI 인자 없이 실행하면 숫자 태그 버그를 재현하는 데모를 돌린다."""
    import tempfile

    demo_content = """---
title: 데모 글
categories: [Quick, Development]
tags: [회고, 2026, 1]
---

본문 내용.
"""
    with tempfile.TemporaryDirectory() as tmp:
        demo_path = Path(tmp) / "2026-01-01-demo.md"
        demo_path.write_text(demo_content, encoding="utf-8")

        print("=== 검사 (수정 전) ===")
        lint_paths([demo_path], fix=False)

        print("=== --fix 적용 ===")
        lint_paths([demo_path], fix=True)

        print("=== 수정 후 frontmatter ===")
        print(demo_path.read_text(encoding="utf-8").split("---")[1].strip())


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        raise SystemExit(main())
    _demo()
