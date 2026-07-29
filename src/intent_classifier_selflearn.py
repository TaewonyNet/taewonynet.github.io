#!/usr/bin/env python3
"""부분문자열 키워드 매칭 우선 + 임베딩 유사도 폴백 + 오분류 자가학습 분류기.

1계층: `keyword_map`에 등록된 키워드가 입력 텍스트에 부분문자열로 포함되면
       즉시 해당 의도로 분류한다.
2계층: 1계층에서 못 잡으면 목(mock) 코사인 유사도 함수로 의도별 대표 문장과
       비교해 가장 유사한 의도를 고른다.
학습:  `learn()`으로 오분류 사례를 알려주면 정답 의도의 키워드 목록에
       입력 텍스트에서 뽑은 키워드를 추가해 다음부터 1계층에서 잡히게 한다.

requirements: 표준 라이브러리만 사용 (실제 bge-m3 임베딩 대신 해시 기반 목 벡터)
"""
from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

WORD_RE = re.compile(r"[\w가-힣]+")


def _mock_embed(text: str, dims: int = 32) -> list[float]:
    """실제 임베딩 모델(bge-m3 등) 없이도 동작을 보여주기 위한 목 임베딩.

    같은 단어를 공유하는 텍스트끼리는 벡터가 유사하도록 단어별 해시를
    차원에 누적하는 방식으로 만든다. 실제 모델로 교체할 자리다.
    """
    vec = [0.0] * dims
    for word in WORD_RE.findall(text.lower()):
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        vec[h % dims] += 1.0
    return vec


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class IntentClassifier:
    """2계층(키워드 -> 임베딩) 의도 분류기 + 오분류 자가학습."""

    def __init__(self, intent_examples: dict[str, list[str]]) -> None:
        """intent_examples: 의도 이름 -> 대표 예시 문장 리스트."""
        self.intent_examples = {k: list(v) for k, v in intent_examples.items()}
        self.keyword_map: dict[str, str] = {}  # 키워드 -> 의도
        self._misclassification_log: list[tuple[str, str, str]] = []  # (text, predicted, correct)

    def _keyword_match(self, text: str) -> str | None:
        """등록된 키워드가 텍스트에 부분문자열로 포함되는지 확인한다."""
        for keyword, intent in self.keyword_map.items():
            if keyword in text:
                return intent
        return None

    def _embedding_fallback(self, text: str) -> str:
        """의도별 대표 문장들과 목 코사인 유사도를 계산해 최고 점수 의도를 고른다."""
        text_vec = _mock_embed(text)
        best_intent, best_score = None, -1.0
        for intent, examples in self.intent_examples.items():
            for example in examples:
                score = _cosine_similarity(text_vec, _mock_embed(example))
                if score > best_score:
                    best_intent, best_score = intent, score
        return best_intent or "unknown"

    def classify(self, text: str) -> str:
        """1계층 키워드 매칭 -> 실패 시 2계층 임베딩 유사도 순으로 분류한다."""
        matched = self._keyword_match(text)
        if matched is not None:
            logger.info("키워드 매칭: %r -> %s", text, matched)
            return matched

        predicted = self._embedding_fallback(text)
        logger.info("임베딩 폴백: %r -> %s", text, predicted)
        return predicted

    def learn(self, text: str, correct_intent: str) -> str:
        """오분류 사례를 학습해 키워드를 자가 등록한다.

        분류 결과가 correct_intent와 다르면, 텍스트에서 가장 긴 단어를
        새 키워드로 뽑아 keyword_map에 등록한다(간단한 TF-IDF 대용 휴리스틱).
        반환값은 등록된 키워드(등록하지 않았으면 빈 문자열).
        """
        predicted = self.classify(text)
        if predicted == correct_intent:
            return ""

        self._misclassification_log.append((text, predicted, correct_intent))
        words = [w for w in WORD_RE.findall(text) if len(w) >= 2]
        if not words:
            return ""
        new_keyword = max(words, key=len)
        self.keyword_map[new_keyword] = correct_intent
        logger.info(
            "자가학습: 오분류(%s -> %s) 감지, 키워드 %r 등록",
            predicted, correct_intent, new_keyword,
        )
        return new_keyword

    def stats(self) -> dict[str, int]:
        return {
            "keyword_count": len(self.keyword_map),
            "misclassification_count": len(self._misclassification_log),
        }


if __name__ == "__main__":
    clf = IntentClassifier(
        intent_examples={
            "web_search": ["최신 뉴스를 검색해줘", "실시간 정보를 찾아줘"],
            "small_talk": ["오늘 기분이 어때", "심심한데 얘기 좀 하자"],
        }
    )

    query = "오늘 날씨 어때"  # "어때"가 small_talk 예시와 겹쳐 실제로는 web_search여야 함에도 오분류됨

    print("=== 학습 전 분류 ===")
    print(f"{query!r} -> {clf.classify(query)}")

    print("\n=== 오분류 학습 ===")
    learned = clf.learn(query, correct_intent="web_search")
    print(f"등록된 키워드: {learned!r}")

    print("\n=== 학습 후 재분류 ===")
    print(f"{query!r} -> {clf.classify(query)}")
    print(f"통계: {clf.stats()}")
