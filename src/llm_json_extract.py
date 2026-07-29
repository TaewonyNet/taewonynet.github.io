"""LLM 응답 문자열에서 JSON 객체를 3단계 폴백(직접 파싱 -> 코드블록 -> 중괄호 추적)으로 추출한다."""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_balanced_braces(text: str) -> str | None:
    """첫 '{' 부터 중괄호 깊이를 세어 깊이가 0으로 돌아오는 지점까지 슬라이싱한다."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> dict | None:
    """
    LLM 응답에서 JSON 객체를 추출한다.

    순서: 1) json.loads 직접 파싱 2) 마크다운 코드블록(```json ... ```) 추출 후 재파싱
    3) 첫 '{'부터 중괄호 균형을 추적해 첫 완결 JSON 객체를 슬라이싱 후 재파싱.

    세 단계 모두 실패하면 None을 반환한다. 재프롬프트(모델에 재요청해 다시 받기)는
    이 함수의 책임이 아니다 — 호출자가 None을 받았을 때 처리해야 한다.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        logger.debug("1단계(직접 파싱) 실패, 코드블록 추출 시도")

    match = CODE_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            logger.debug("2단계(코드블록 추출) 실패, 중괄호 추적 시도")

    candidate = _extract_balanced_braces(text)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            logger.debug("3단계(중괄호 추적)도 실패")

    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    samples = {
        "직접 파싱 성공": '{"name": "taewony", "role": "engineer"}',
        "코드블록으로 감쌈": '여기 결과입니다.\n```json\n{"ok": true, "count": 3}\n```\n감사합니다.',
        "앞뒤에 설명 텍스트": '결과: {"status": "done", "items": [1, 2, 3]} 이상입니다.',
        "완전히 파싱 불가": "죄송합니다, JSON을 생성할 수 없습니다.",
    }

    for label, text in samples.items():
        result = extract_json(text)
        print(f"[{label}] -> {result}")
