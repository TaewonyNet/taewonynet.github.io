#!/usr/bin/env python3
"""막힌 원인별로 대안 전략을 분류해 반환하는 최소 PoC."""

from __future__ import annotations

import logging
from enum import Enum

logger = logging.getLogger(__name__)


class BlockReason(str, Enum):
    """수집이 막힌 원인 유형."""

    BOT_DETECTION = "bot_detection"
    ROBOTS_BLOCK = "robots_block"
    CORS = "cors"
    LOGIN_WALL = "login_wall"
    LEGAL_RESTRICTION = "legal_restriction"


# 원인 유형 → (대안 전략 이름, 한 줄 설명)
_STRATEGY_MAP: dict[BlockReason, tuple[str, str]] = {
    BlockReason.BOT_DETECTION: (
        "stealth_or_real_profile",
        "StealthyFetcher 또는 real_profile 단계로 폴백해 브라우저 지문을 실제처럼 흉내낸다.",
    ),
    BlockReason.ROBOTS_BLOCK: (
        "respect_or_seek_api",
        "robots.txt 명시 차단이면 우회 대신 공식 API·RSS 등 허용된 경로를 찾는다.",
    ),
    BlockReason.CORS: (
        "server_side_request",
        "브라우저 정책이므로 클라이언트 수집을 포기하고 서버(백엔드)에서 직접 요청한다.",
    ),
    BlockReason.LOGIN_WALL: (
        "manual_cookie_or_bookmarklet",
        "계정이 있으면 세션 쿠키를 추출해 재사용하거나, 브라우저 내부에서 북마크릿으로 수집한다.",
    ),
    BlockReason.LEGAL_RESTRICTION: (
        "abandon_or_request_permission",
        "기술적 우회가 가능해도 법적 위험이 남는다. 수집을 포기하거나 정식으로 허가를 구한다.",
    ),
}


def suggest_alternative(reason: BlockReason | str) -> tuple[str, str]:
    """막힌 원인을 받아 (대안 전략 이름, 설명)을 반환한다.

    문자열로 넘겨도 BlockReason으로 변환해 처리한다. 알 수 없는 값이면 ValueError.
    """
    if isinstance(reason, str):
        try:
            reason = BlockReason(reason)
        except ValueError as exc:
            valid = ", ".join(r.value for r in BlockReason)
            raise ValueError(f"알 수 없는 원인: {reason!r}. 가능한 값: {valid}") from exc

    strategy_name, description = _STRATEGY_MAP[reason]
    logger.info("원인=%s → 전략=%s", reason.value, strategy_name)
    return strategy_name, description


def diagnose_from_symptom(status_code: int | None, redirected_to_login: bool, is_cors_error: bool) -> BlockReason:
    """관측 가능한 증상(상태 코드·리다이렉트·CORS 여부)만으로 원인을 추정한다."""
    if is_cors_error:
        return BlockReason.CORS
    if redirected_to_login:
        return BlockReason.LOGIN_WALL
    if status_code == 403:
        return BlockReason.BOT_DETECTION
    if status_code == 451:
        return BlockReason.LEGAL_RESTRICTION
    return BlockReason.BOT_DETECTION


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    cases = [
        ("bot_detection", None, False, False),
        ("cors", None, False, True),
        ("login_wall", None, True, False),
    ]
    for reason_str, status, redirected, cors in cases:
        name, desc = suggest_alternative(reason_str)
        print(f"[{reason_str}] 전략={name}\n  설명: {desc}")

    print("\n증상 기반 추정:")
    guessed = diagnose_from_symptom(status_code=403, redirected_to_login=False, is_cors_error=False)
    name, desc = suggest_alternative(guessed)
    print(f"status=403 → 추정 원인={guessed.value} → 전략={name}")
