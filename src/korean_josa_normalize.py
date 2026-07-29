"""한국어 조사를 어절 끝에서 제거해 색인/쿼리 토큰을 일치시키는 정규화 PoC."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# 긴 조사부터 매칭해야 짧은 조사가 먼저 걸려 잘못 잘리는 걸 막는다.
JOSA_LIST = sorted(
    [
        "으로부터", "에서부터",
        "이라는", "라는",
        "에게서", "한테서",
        "으로는", "에서는", "에게는", "한테는",
        "으로", "로서", "로써",
        "에서", "에게", "한테", "에는", "에도", "에만",
        "이나", "나마",
        "이란", "란",
        "이든", "든",
        "이라도", "라도",
        "까지", "부터", "마저", "조차", "밖에",
        "이라", "라",
        "이랑", "랑",
        "와는", "과는",
        "은", "는", "이", "가", "을", "를", "의", "에", "도", "만", "와", "과",
    ],
    key=len,
    reverse=True,
)

_WORD_RE = re.compile(r"\S+")


def strip_josa(word: str) -> str:
    """어절 끝에서 가장 긴 조사부터 매칭해 제거한다. 매칭 안 되면 원어절 그대로 반환한다."""
    for josa in JOSA_LIST:
        if len(word) > len(josa) and word.endswith(josa):
            return word[: -len(josa)]
    return word


def normalize_korean(text: str) -> str:
    """텍스트의 각 어절에 strip_josa를 적용한다. 색인 시점과 쿼리 시점에 동일하게 써야 효과가 있다."""
    words = _WORD_RE.findall(text)
    return " ".join(strip_josa(w) for w in words)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    samples = ["마트를", "마트에서", "마트로", "마트까지", "마트는", "마트"]
    print("어절 단위 조사 제거:")
    for word in samples:
        print(f"  {word!r:<12} -> {strip_josa(word)!r}")

    query = "근처 마트에서 파는 우유 가격을 알려줘"
    doc = "이 마트를 방문한 고객은 우유를 주로 구매한다"
    print(f"\n원문 쿼리: {query!r}")
    print(f"정규화 쿼리: {normalize_korean(query)!r}")
    print(f"원문 문서: {doc!r}")
    print(f"정규화 문서: {normalize_korean(doc)!r}")
