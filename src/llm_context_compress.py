#!/usr/bin/env python3
"""목표 토큰 수에 맞춰 긴 텍스트를 압축하는 추출요약(extractive summary) 폴백.

LLMLingua-2 같은 압축 모델이 없는 환경(오프라인·모델 다운로드 실패)에서도
동작하도록, 문장 단위로 쪼개 간단한 휴리스틱(문장 길이·키워드 빈도)으로
중요도 점수를 매기고, 점수 높은 문장부터 목표 토큰 수(단어 수로 근사)에
맞을 때까지 원문 순서를 지켜 채워 넣는다.

requirements: 표준 라이브러리만 사용
"""
from __future__ import annotations

import logging
import re
from collections import Counter

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?다요])\s+")
WORD_RE = re.compile(r"[\w가-힣]+")

# 문장 중요도 판단에서 제외할 흔한 조사·어미 성격의 짧은 토큰
STOPWORDS = {"이", "가", "은", "는", "을", "를", "그리고", "그러나", "하지만"}


def split_sentences(text: str) -> list[str]:
    """텍스트를 문장 단위로 분리한다. 빈 문장은 제거한다."""
    parts = SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def count_tokens(text: str) -> int:
    """토큰 수를 단어 수로 근사한다."""
    return len(WORD_RE.findall(text))


def score_sentences(sentences: list[str]) -> list[float]:
    """문장 길이·키워드 빈도 기반 휴리스틱으로 중요도 점수를 매긴다.

    점수 = (문장 내 고빈도 키워드 등장 수) + (문장 길이에 대한 로그 가중치).
    전체 문서에서 자주 등장하는 단어일수록 핵심 키워드로 간주한다.
    """
    all_words: list[str] = []
    for sent in sentences:
        all_words.extend(w for w in WORD_RE.findall(sent) if w not in STOPWORDS)
    freq = Counter(all_words)

    scores = []
    for sent in sentences:
        words = [w for w in WORD_RE.findall(sent) if w not in STOPWORDS]
        keyword_score = sum(freq[w] for w in words)
        length_score = len(words) ** 0.5  # 너무 짧은 문장이 과도하게 뽑히지 않도록 완화
        scores.append(keyword_score + length_score)
    return scores


def compress_to_budget(text: str, target_tokens: int) -> str:
    """목표 토큰 수에 맞춰 텍스트를 추출요약으로 압축한다.

    중요도 순으로 문장을 고르되, 최종 출력은 원문 순서를 유지해
    문맥이 어색해지지 않게 한다. 원문이 이미 목표보다 짧으면 그대로 반환한다.
    """
    if count_tokens(text) <= target_tokens:
        return text

    sentences = split_sentences(text)
    if not sentences:
        return text

    scores = score_sentences(sentences)
    ranked_idx = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)

    selected: set[int] = set()
    used_tokens = 0
    for idx in ranked_idx:
        tok = count_tokens(sentences[idx])
        if used_tokens + tok > target_tokens and selected:
            continue
        selected.add(idx)
        used_tokens += tok
        if used_tokens >= target_tokens:
            break

    ordered = [sentences[i] for i in sorted(selected)]
    result = " ".join(ordered)
    logger.info(
        "압축 완료: 원본 %d토큰 -> %d토큰 (문장 %d개 중 %d개 선택)",
        count_tokens(text), count_tokens(result), len(sentences), len(selected),
    )
    return result


if __name__ == "__main__":
    sample = (
        "RAG 파이프라인은 검색된 문서를 LLM 컨텍스트에 그대로 넣는다. "
        "문서가 길어지면 토큰 한도를 초과하거나 비용이 급증한다. "
        "단순히 앞부분만 자르면 중요한 정보가 중간이나 뒤쪽에 있을 때 손실이 크다. "
        "압축 모델은 문장 단위 중요도를 계산해 핵심만 남긴다. "
        "이 예시는 실제 모델 없이 길이와 키워드 빈도만으로 근사한 결과를 보여준다. "
        "키워드가 반복되는 문장일수록 문서의 핵심 주제를 담고 있을 가능성이 높다. "
        "짧은 감탄사나 접속사로만 이루어진 문장은 정보량이 적어 낮은 점수를 받는다."
    )
    print(f"원문 토큰 수: {count_tokens(sample)}")
    for budget in (30, 15):
        compressed = compress_to_budget(sample, budget)
        print(f"\n목표 {budget}토큰 -> 실제 {count_tokens(compressed)}토큰")
        print(compressed)
