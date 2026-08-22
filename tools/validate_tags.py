#!/usr/bin/env python3
# 원본: agent-playground/Blog/scripts/ — 이 파일은 CI 실행용 사본이다.
# 규칙을 바꿀 때는 원본을 고치고 다시 복사한다. 한쪽만 고치지 않는다.
"""태그 스키마 검증기 — TAGGING.md §6.2 V3.

`.md` 프론트매터만 읽어 검사한다(외부 상태 불필요, 제약 C3).

  ① domain·purpose 존재
  ② 닫힌 어휘 소속
  ③ 자유 태그 표기 규칙 — 하이픈만·소문자만·숫자단독 금지·별칭 금지·금지어 금지
  ④ 자유 태그 수 0~7

사용:
    python3 scripts/validate_tags.py <파일|디렉터리> ...
    python3 scripts/validate_tags.py --stats <디렉터리>   # G5 IDF 붕괴 검사 함께
"""

from __future__ import annotations

import argparse
import collections
import json
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

VOCAB_PATH = Path(__file__).parent / "tag_vocabulary.json"
FM_RE = re.compile(r"\A---\n(.*?)\n---", re.S)
TAG_RE = re.compile(r"^tags:\s*\[(.*?)\]\s*$", re.M)
SCALAR_RE = "^{key}:\\s*(.+?)\\s*$"
GOOD_TAG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_FREE_TAGS = 7  # 실측(2026-08-21): 정규화 후 최대 7개. 임의 절단보다 실태에 맞춘 상한.
IDF_COLLAPSE_RATIO = 0.5


def load_vocab() -> dict:
    with VOCAB_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def parse_frontmatter(text: str) -> dict | None:
    """프론트매터를 최소 파싱한다. PyYAML 없이 동작하도록 필요한 키만 뽑는다."""
    m = FM_RE.search(text)
    if not m:
        return None
    fm = m.group(1)
    out: dict = {}
    for key in ("domain", "purpose", "title"):
        km = re.search(SCALAR_RE.format(key=key), fm, re.M)
        if km:
            out[key] = km.group(1).strip().strip("'\"")
    tm = TAG_RE.search(fm)
    out["tags"] = (
        [t.strip().strip("'\"") for t in tm.group(1).split(",") if t.strip()] if tm else []
    )
    cm = re.search(r"^categories:\s*\[(.*?)\]\s*$", fm, re.M)
    out["categories"] = (
        [c.strip().strip("'\"") for c in cm.group(1).split(",") if c.strip()] if cm else []
    )
    return out


def check(path: Path, vocab: dict) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    fm = parse_frontmatter(text)
    if fm is None:
        return ["프론트매터 없음"]
    if "Movie" in fm["categories"]:
        return []  # 영화 글은 이 스키마 대상이 아니다

    errs: list[str] = []
    for axis in ("domain", "purpose"):
        val = fm.get(axis)
        if not val:
            errs.append(f"{axis} 누락")
        elif val not in vocab[axis]:
            errs.append(f"{axis} 어휘 밖: {val!r}")

    tags = fm["tags"]
    if len(tags) > MAX_FREE_TAGS:
        errs.append(f"자유 태그 {len(tags)}개 (최대 {MAX_FREE_TAGS})")
    for t in tags:
        if t in vocab["tag_banned"]:
            errs.append(f"금지 태그: {t!r}")
        elif t in vocab["tag_aliases"]:
            errs.append(f"별칭 태그: {t!r} → {vocab['tag_aliases'][t]!r} 로 바꿀 것")
        elif not GOOD_TAG_RE.match(t):
            errs.append(f"표기 위반: {t!r} (소문자·하이픈만)")
        elif t.isdigit():
            errs.append(f"숫자 태그: {t!r}")
    return errs


def is_hidden(path: Path) -> bool:
    """`.ipynb_checkpoints` 등 점 디렉터리 안의 파일은 Jekyll도 무시한다."""
    return any(part.startswith(".") for part in path.parts)


def collect(targets: list[str]) -> list[Path]:
    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files.extend(f for f in sorted(p.rglob("*.md")) if not is_hidden(f.relative_to(p)))
        else:
            files.append(p)
    return files


def report_stats(files: list[Path], vocab: dict) -> int:
    """G5(IDF 붕괴) · G6(드리프트) 지표."""
    axes = {"domain": collections.Counter(), "purpose": collections.Counter()}
    total = off_vocab = 0
    for path in files:
        fm = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if fm is None or "Movie" in fm["categories"]:
            continue
        total += 1
        bad = False
        for axis in axes:
            val = fm.get(axis)
            if val:
                axes[axis][val] += 1
                if val not in vocab[axis]:
                    bad = True
            else:
                bad = True
        off_vocab += bad

    if not total:
        return 0
    logger.info("\n=== 지표 (대상 %d편) ===", total)
    rc = 0
    for axis, counter in axes.items():
        logger.info("[%s] 사용 %d값", axis, len(counter))
        for val, n in counter.most_common():
            ratio = n / total
            flag = "  ← G5 위반(50% 초과)" if ratio > IDF_COLLAPSE_RATIO else ""
            logger.info("   %-16s %3d (%4.1f%%)%s", val, n, 100 * ratio, flag)
            if ratio > IDF_COLLAPSE_RATIO:
                rc = 1
    drift = off_vocab / total
    logger.info(
        "드리프트(축 누락·어휘 밖): %d/%d = %.1f%%%s",
        off_vocab, total, 100 * drift,
        "  ← G6 위반(5% 초과)" if drift > 0.05 else "",
    )
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--stats", action="store_true", help="G5·G6 지표도 출력")
    args = ap.parse_args()

    vocab = load_vocab()
    files = collect(args.targets)
    fails = 0
    for path in files:
        errs = check(path, vocab)
        if errs:
            fails += 1
            logger.info("FAIL  %s", path.name)
            for e in errs:
                logger.info("        - %s", e)
    checked = len(files)
    logger.info("\n총 %d개 — FAIL %d / PASS %d", checked, fails, checked - fails)

    rc = 1 if fails else 0
    if args.stats:
        rc = max(rc, report_stats(files, vocab))
    return rc


if __name__ == "__main__":
    sys.exit(main())
