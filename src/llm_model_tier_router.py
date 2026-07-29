"""런타임에 발견한 LLM 모델명을 tier(cheap/standard/premium)로 자동 분류하고 라우팅한다."""
from __future__ import annotations

import logging
from typing import Callable, Iterable

logger = logging.getLogger(__name__)

# tier 오름차순 — cheap < standard < premium
TIER_ORDER: list[str] = ["cheap", "standard", "premium"]

# 모델명에 포함된 키워드로 tier를 판정한다. standard는 기본값(매칭 없을 때)이라 여기 없음.
TIER_KEYWORDS: dict[str, tuple[str, ...]] = {
    "premium": ("pro", "opus", "ultra"),
    "cheap": ("mini", "flash", "haiku", "nano", "lite"),
}
DEFAULT_TIER = "standard"


def classify_tier(model_name: str) -> str:
    """모델명 키워드로 tier를 분류한다. 매칭되는 키워드가 없으면 standard로 간주한다."""
    name = model_name.lower()
    for tier, keywords in TIER_KEYWORDS.items():
        if any(keyword in name for keyword in keywords):
            return tier
    return DEFAULT_TIER


def discover_and_classify(list_models: Callable[[], Iterable[str]]) -> dict[str, list[str]]:
    """provider.list_models() 결과를 순회하며 tier별 버킷으로 묶는다."""
    buckets: dict[str, list[str]] = {tier: [] for tier in TIER_ORDER}
    for name in list_models():
        tier = classify_tier(name)
        buckets[tier].append(name)
        logger.debug("model=%s tier=%s", name, tier)
    return buckets


def route(buckets: dict[str, list[str]], requested_tier: str) -> str | None:
    """요청 tier에 가용 모델이 없으면 상위(더 비싼) tier로 순차 업그레이드한다."""
    if requested_tier not in TIER_ORDER:
        requested_tier = DEFAULT_TIER
    start = TIER_ORDER.index(requested_tier)
    for tier in TIER_ORDER[start:]:
        candidates = buckets.get(tier) or []
        if candidates:
            return candidates[0]
    return None


class DummyProvider:
    """실제 공급자 SDK 대신 고정된 모델 목록을 돌려주는 더미 provider."""

    def list_models(self) -> list[str]:
        return [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gpt-4-mini",
            "claude-3-haiku",
            "llama-3-70b",  # 키워드 없음 -> standard
        ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    provider = DummyProvider()
    buckets = discover_and_classify(provider.list_models)

    print("발견된 모델의 tier 분류:")
    for tier in TIER_ORDER:
        print(f"  {tier:<8} {buckets[tier]}")

    for requested in ("cheap", "standard", "premium"):
        chosen = route(buckets, requested)
        print(f"requested_tier={requested:<8} -> chosen_model={chosen}")

    # cheap tier가 비어 있을 때 상위로 업그레이드되는지 확인
    empty_cheap = {"cheap": [], "standard": ["gpt-4-mini-standin"], "premium": ["gemini-2.5-pro"]}
    print("cheap 버킷이 비었을 때:", route(empty_cheap, "cheap"))
