#!/usr/bin/env python3
# 원본: agent-playground/Blog/scripts/ — 이 파일은 CI 실행용 사본이다.
# 규칙을 바꿀 때는 원본을 고치고 다시 복사한다. 한쪽만 고치지 않는다.
"""글 구조·발행 게이트 검사기 — WRITING.md §4 골격 + §8 발행 체크리스트.

사람 판단 대신 이 스크립트가 최종 게이트다. 과거 21편이 이 검사 없이 라벨을
임의로 생략·축약해 구조가 틀어진 전례가 있다(WRITING.md §8).

검사 두 층:
  [ERROR] 구조 위반 — §4 4단 골격 라벨 누락, `source:` 금지 필드, 이모티콘
  [WARN ] 발행 게이트 — 측정 수치·표·샘플 코드 링크·정중체 등 권고 항목

트랙은 `categories` 프론트매터로 갈린다(Quick / Deep / Diary).

사용:
    python3 scripts/validate_template.py <파일|디렉터리> ...
    python3 scripts/validate_template.py --strict <경로>   # WARN도 실패로 처리
    python3 scripts/validate_template.py --quiet <경로>    # FAIL만 출력
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

FM_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)

# ── §4 4단 공통 골격 (Quick·Deep) ─────────────────────────────────────────────
COMMON_MARKERS: list[tuple[str, str]] = [
    ("H2 제목", r"^##\s+\S"),
    ("§1 서론 헤딩", r"^###\s*1\.\s*서론"),
    ("문제/상황 (Problem)", r"\*\*문제/상황\s*\(Problem\)"),
    ("목적 (Purpose)", r"\*\*목적\s*\(Purpose\)"),
    ("대상 (Target Audience)", r"\*\*대상\s*\(Target Audience\)"),
    ("§2 방법 및 과정 헤딩", r"^###\s*2\.\s*방법 및 과정"),
    ("배경 조사 및 데이터", r"\*\*배경 조사 및 데이터\s*\(Data Collection\)"),
    ("접근 방법", r"\*\*접근 방법\s*\(Approach Methods\)"),
    ("[방법 1]", r"\*\*\[방법 1\]"),
    ("[방법 2]", r"\*\*\[방법 2\]"),
    ("분석 및 해결 프로세스", r"\*\*분석 및 해결 프로세스\s*\(Analysis Flow\)"),
    ("도구/기술", r"\*\*도구/기술"),
    ("주요 단계", r"\*\*주요 단계"),
    ("결과 도출 및 검증", r"\*\*결과 도출 및 검증"),
    ("§3 결과 헤딩", r"^###\s*3\.\s*결과"),
    ("분석 결과 요약", r"\*\*분석 결과 요약"),
    ("§4 인사이트 및 액션 헤딩", r"^###\s*4\.\s*인사이트 및 액션"),
    ("인사이트 (Insight)", r"\*\*인사이트\s*\(Insight"),
    ("실행 방안 (Action Plan)", r"\*\*실행 방안\s*\(Action Plan\)"),
    ("한 줄 결론 (Key Takeaway)", r"\*\*한 줄 결론\s*\(Key Takeaway\)"),
    ("다음 스텝 (Next Step)", r"\*\*다음 스텝\s*\(Next Step\)"),
]

# ── §5 Diary·회고 변형 ───────────────────────────────────────────────────────
RETRO_MARKERS: list[tuple[str, str]] = [
    ("H2 제목", r"^##\s+\S"),
    ("§1 서론 헤딩", r"^###\s*1\.\s*서론"),
    # §5 "서론: 올해의 테마/목표 복기" — 둘 다 정상 표기다.
    ("목표 복기 또는 테마", r"\*\*.*(목표 복기|테마)"),
    ("배경/상황", r"\*\*배경/상황"),
    ("§2 주요 과정과 사건 헤딩", r"^###\s*2\.\s*주요 과정과 사건"),
    ("달성한 것", r"\*\*달성한 것"),
    ("겪은 이슈와 어려움", r"\*\*겪은 이슈와 어려움"),
    ("§3 결과 헤딩", r"^###\s*3\.\s*결과"),
    ("객관적 성과 요약", r"\*\*객관적 성과 요약"),
    ("주관적 변화", r"\*\*주관적 변화"),
    ("§4 인사이트 및 액션 헤딩", r"^###\s*4\.\s*인사이트 및 액션"),
    ("주요 인사이트", r"\*\*주요 인사이트"),
    ("실행 방안 (Action Plan)", r"\*\*실행 방안\s*\(Action Plan\)"),
    ("한 줄 결론 (Key Takeaway)", r"\*\*한 줄 결론\s*\(Key Takeaway\)"),
    ("다음 스텝 (Next Step)", r"\*\*다음 스텝\s*\(Next Step\)"),
]

# ── Diary·목표 변형 ──────────────────────────────────────────────────────────
# WRITING.md §5는 Diary를 "개인 회고·목표"로 묶어놓고 회고 구조만 규정한다.
# 목표 글은 실제로 구조가 다르다(문제 및 분석 → 구체적 목표). 표본이 1편뿐이라
# 안쪽 라벨까지 못박지 않고 공통 뼈대만 검사한다. §5에 목표 규격이 생기면 조인다.
GOAL_MARKERS: list[tuple[str, str]] = [
    ("H2 제목", r"^##\s+\S"),
    ("§1 서론 헤딩", r"^###\s*1\.\s*서론"),
    ("§2 헤딩", r"^###\s*2\.\s+\S"),
    ("§3 헤딩", r"^###\s*3\.\s+\S"),
    ("§4 인사이트 헤딩", r"^###\s*4\.\s*인사이트"),
    ("주요 인사이트", r"\*\*주요 인사이트"),
    ("한 줄 결론 (Key Takeaway)", r"\*\*한 줄 결론\s*\(Key Takeaway\)"),
]

# §4 4단 템플릿 도입 이전 글. WRITING.md §1이 문체 출처로 인용하고 §2가 정중체
# 잔존을 명시적으로 인정한다. 소급 개편 대상이 아니므로 LEGACY로 따로 표시한다.
LEGACY = {
    "2024-01-20-AWS-Athena-Guide.md",
    "2025-07-29-Athena-Json-Parse.md",
}

# 이모티콘: WRITING.md §6 "이모티콘 금지"
# 화살표(U+2190~21FF, U+2B00~2BFF)는 제외한다 — §7이 `주요 단계`에 `$\rightarrow$`/`→`를
# 쓰도록 규정하므로 정상 표기다.
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF"
    "\U00002600-\U000026FF\U00002700-\U000027BF\U0000FE0F]"
)
SAMPLE_LINK_RE = re.compile(r"\[샘플 코드\]\(https?://[^\s)]+\)")
CODE_FENCE_RE = re.compile(r"^```", re.M)
POLITE_RE = re.compile(r"(습니다|합니다|입니다)[.,\s]")
TABLE_RE = re.compile(r"^\s*\|.+\|\s*$", re.M)
# §8 "비교/추천은 표로 정리됐는가" — 비교 성격 글에만 해당한다.
# 전 글에 무차별로 경고하면 신호가 죽으므로 제목으로 대상을 좁힌다.
COMPARATIVE_RE = re.compile(r"(비교|종류|vs\.?|선택|고르|사다리|정리해보자)", re.I)
DIGIT_RE = re.compile(r"\d")
# 기밀: CLAUDE.md §4 — 티켓번호·내부 식별자 직접 표기 금지
SECRET_RE = re.compile(r"\b(TDT-\d+|PRIVIA|omakase|data310|tidesquare)\b", re.I)

MAX_CODE_FENCES = 2  # §5 "본문에 코드를 다 넣지 않는다"

# §5 Quick "짝 소스 필수"의 확정 예외 — PoC 코드가 없는 도구 사용기 4편.
# 본인 판단으로 현상태 유지 결정됨(2026-08).
NO_SOURCE_EXEMPT = {
    "2025-12-18-Atlassian을-MCP로-사용해보자.md",
    "2026-01-10-Cursor-IDE를-사용해보자.md",
    "2026-01-12-Opencode를-사용해보자.md",
    "2026-01-14-Oh-My-Opencode를-사용해보자.md",
}

FENCE_BLOCK_RE = re.compile(r"^```.*?^```", re.S | re.M)
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def prose_only(body: str) -> str:
    """코드 블록·인라인 코드를 걷어낸 산문만 남긴다.

    문체 규칙은 저자가 쓴 문장에만 적용된다. 코드나 인용된 출력 예시
    (예: LLM 응답 샘플 `결과: {...} 이상입니다.`)를 문체 위반으로 잡으면 오탐이다.
    """
    return INLINE_CODE_RE.sub(" ", FENCE_BLOCK_RE.sub(" ", body))


def parse(text: str) -> tuple[dict, str] | None:
    m = FM_RE.match(text)
    if not m:
        return None
    fm_raw, body = m.group(1), m.group(2)
    fm: dict = {"_raw": fm_raw}
    c = re.search(r"^categories:\s*\[(.*?)\]\s*$", fm_raw, re.M)
    fm["categories"] = (
        [x.strip().strip("'\"") for x in c.group(1).split(",") if x.strip()] if c else []
    )
    for key in ("title", "visibility", "asset"):
        k = re.search(rf"^{key}:\s*(.+?)\s*$", fm_raw, re.M)
        if k:
            fm[key] = k.group(1).strip().strip("'\"")
    return fm, body


def check(path: Path) -> tuple[list[str], list[str]]:
    """(errors, warnings) 반환."""
    parsed = parse(path.read_text(encoding="utf-8", errors="replace"))
    if parsed is None:
        return (["프론트매터 없음"], [])
    fm, body = parsed
    cats = fm["categories"]
    if "Movie" in cats:
        return ([], [])  # 영화 글은 이 템플릿 대상이 아니다

    # 트랙 분기는 하위 카테고리까지 본다 — `[Diary]`만 붙고 공통 4단 골격을 쓰는
    # 글이 실재하므로("글을 써 보자"), "Diary" 유무만으로 갈라선 안 된다.
    is_retro = "회고" in cats
    is_goal = "목표" in cats
    is_diary = is_retro or is_goal
    is_deep = "Deep" in cats
    is_quick = "Quick" in cats

    errors: list[str] = []
    warns: list[str] = []

    # ── 구조 (§4 / §5) ──
    markers = RETRO_MARKERS if is_retro else GOAL_MARKERS if is_goal else COMMON_MARKERS
    missing = [name for name, pat in markers if not re.search(pat, body, re.M)]
    if missing:
        errors.append(f"골격 라벨 누락 {len(missing)}개: {', '.join(missing)}")

    # ── 금지 (§7 / §6 / CLAUDE.md §4) ──
    if re.search(r"^source:", fm["_raw"], re.M):
        errors.append("frontmatter에 `source:` 필드 (§7 금지 — 샘플 코드 링크로만)")
    for e in set(EMOJI_RE.findall(body)):
        errors.append(f"이모티콘 사용: {e!r} (§6 금지)")
    # 프론트매터도 검사한다 — title·description 은 SEO 메타로 공개된다.
    for s in set(SECRET_RE.findall(fm["_raw"] + "\n" + body)):
        errors.append(f"내부 식별자 노출: {s!r} (CLAUDE.md §4)")

    # ── Deep 전용 (§5) ──
    if is_deep:
        if "visibility" not in fm:
            errors.append("Deep 트랙인데 `visibility` 없음 (§5)")
        elif fm["visibility"] not in ("private", "review", "public"):
            errors.append(f"visibility 값 오류: {fm['visibility']!r}")
        if not re.search(r"한계|Limitations", body):
            warns.append("Deep 트랙 권고: 인사이트에 한계(Limitations) 없음 (§5)")

    # ── 발행 게이트 (§8) ──
    if not DIGIT_RE.search(body):
        warns.append("측정 수치가 하나도 없음 (§8 — 추상 표현 대신 측정값)")
    if (not TABLE_RE.search(body) and not is_diary
            and COMPARATIVE_RE.search(fm.get("title", ""))):
        warns.append("비교 성격 글인데 표 없음 (§8 — 비교/추천은 표로)")
    if POLITE_RE.search(prose_only(body)):
        warns.append("정중체(~습니다/~입니다) 사용 (§2 — 신규 글은 단정형/명사형)")
    fences = len(CODE_FENCE_RE.findall(body))
    if fences > MAX_CODE_FENCES:
        warns.append(f"코드 블록 {fences // 2}개 (§5 — 본문엔 핵심 몇 줄만, 전체는 링크로)")
    if is_quick and path.name not in NO_SOURCE_EXEMPT and not SAMPLE_LINK_RE.search(body):
        warns.append("한 줄 결론에 [샘플 코드] 링크 없음 (§5 Quick — 짝 소스 필수)")

    return errors, warns


def collect(targets: list[str]) -> list[Path]:
    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_dir():
            files.extend(
                f
                for f in sorted(p.rglob("*.md"))
                if not any(part.startswith(".") for part in f.relative_to(p).parts)
                and f.name != "_template.md"
            )
        else:
            files.append(p)
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="+")
    ap.add_argument("--strict", action="store_true", help="WARN도 실패로 처리")
    ap.add_argument("--quiet", action="store_true", help="FAIL만 출력")
    args = ap.parse_args()

    files = collect(args.targets)
    fails = warn_only = passed = skipped = legacy = 0

    for path in files:
        errors, warns = check(path)
        if path.name in LEGACY:
            legacy += 1
            if not args.quiet:
                logger.info("LEGACY  %s  (§4 도입 이전 글 — 소급 대상 아님)", path.name)
            continue
        parsed = parse(path.read_text(encoding="utf-8", errors="replace"))
        if parsed and "Movie" in parsed[0]["categories"]:
            skipped += 1
            continue
        if errors or (args.strict and warns):
            fails += 1
            logger.info("FAIL  %s", path.name)
        elif warns:
            warn_only += 1
            passed += 1
            if not args.quiet:
                logger.info("WARN  %s", path.name)
        else:
            passed += 1
            if not args.quiet:
                logger.info("PASS  %s", path.name)
        if not args.quiet or errors or (args.strict and warns):
            for e in errors:
                logger.info("        ✗ %s", e)
            for w in warns:
                logger.info("        ! %s", w)

    total = passed + fails
    logger.info(
        "\n총 %d편 — PASS %d (경고 %d) / FAIL %d%s%s",
        total, passed, warn_only, fails,
        f" · LEGACY {legacy}편" if legacy else "",
        f" · 영화 {skipped}편 제외" if skipped else "",
    )
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
