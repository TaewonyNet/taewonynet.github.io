#!/usr/bin/env python3
"""scrapling StealthyFetcher의 solve_cloudflare 옵션 조합을 흉내내는 PoC.

StealthyFetcher가 내부적으로 쓰는 브라우저 엔진(scrapling 버전에 따라 다를 수
있다)이 설치돼 있지 않은 환경에서도 파라미터 조합과 폴백 전략 자체는 확인할
수 있게 구성했다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Cloudflare가 함께 확인하는 세 채널을 동시에 막아야 챌린지 없이 통과한다.
CLOUDFLARE_STEALTH_OPTIONS: dict[str, object] = {
    "headless": False,       # headless 감지(navigator.webdriver 등) 우회
    "block_webrtc": True,    # WebRTC로 실제 IP가 새는 것을 차단
    "hide_canvas": True,     # Canvas 지문에 노이즈를 섞어 식별 방지
    "network_idle": True,    # 챌린지 스크립트가 끝까지 실행되도록 대기
    "solve_cloudflare": True,  # Turnstile/Interstitial 챌린지 자동 해결
}


@dataclass
class BypassResult:
    ok: bool
    method: str
    detail: str


def fetch_with_cloudflare_bypass(url: str, options: dict[str, object] | None = None) -> BypassResult:
    """StealthyFetcher.fetch(url, **options)를 호출해 Cloudflare 챌린지를 통과한다.

    scrapling 또는 그 내부 브라우저 엔진이 없으면 폴백 전략을 안내하는 BypassResult를 반환한다.
    """
    options = options or CLOUDFLARE_STEALTH_OPTIONS
    try:
        from scrapling.fetchers import StealthyFetcher
    except ImportError:
        return BypassResult(
            ok=False,
            method="unavailable",
            detail="scrapling이 설치되어 있지 않다. `pip install scrapling` 후 다시 시도한다.",
        )

    try:
        page = StealthyFetcher.fetch(url, **options)
        return BypassResult(ok=True, method="stealth", detail=f"status={page.status}")
    except Exception as exc:  # noqa: BLE001 - 브라우저 엔진 미설치 등 다양한 원인을 하나로 묶어 폴백 안내
        return BypassResult(
            ok=False,
            method="stealth-failed",
            detail=(
                f"StealthyFetcher 실행 실패({exc}). "
                "브라우저 엔진 설치 확인 또는 real_profile 단계로 폴백한다."
            ),
        )


def explain_options(options: dict[str, object] | None = None) -> str:
    """옵션 조합이 각각 무엇을 막는지 사람이 읽을 텍스트로 설명한다 (네트워크 불필요)."""
    options = options or CLOUDFLARE_STEALTH_OPTIONS
    lines = []
    reasons = {
        "headless": "headless=False → navigator.webdriver 등 headless 감지 신호 제거",
        "block_webrtc": "block_webrtc=True → WebRTC로 실제 IP 노출 차단",
        "hide_canvas": "hide_canvas=True → Canvas 지문에 노이즈 삽입",
        "network_idle": "network_idle=True → 챌린지 스크립트 완료까지 대기",
        "solve_cloudflare": "solve_cloudflare=True → Turnstile/Interstitial 자동 해결",
    }
    for key in options:
        lines.append(reasons.get(key, f"{key}={options[key]}"))
    return "\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    print("적용 옵션 설명:")
    print(explain_options())
    print()

    # 실제 네트워크 호출 없이도 로직을 확인할 수 있도록 존재하지 않는 로컬 포트로 시도한다.
    result = fetch_with_cloudflare_bypass("http://127.0.0.1:1/")
    print(f"\n결과: ok={result.ok} method={result.method}")
    print(f"detail: {result.detail}")
