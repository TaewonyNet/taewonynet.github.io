#!/usr/bin/env python3
"""과거 글에서 few-shot 예시를 뽑되 자기 참조·중복 문서를 제외하는 RAG 위생 로직.

`select_fewshot_examples`는 목(mock) 유사도 점수로 corpus를 정렬하고,
`exclude_ids`(자기 자신·주제가 같은 과거 글)를 제외한 뒤, 서로 너무 유사한
예시(중복)를 추가로 걸러 상위 N개만 반환한다. 문체 통계(문장 길이·어미
분포)를 뽑는 보조 함수도 함께 둔다.

requirements: 표준 라이브러리만 사용 (실제 임베딩 대신 자카드 유사도로 근사)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

WORD_RE = re.compile(r"[\w가-힣]+")
ENDING_PATTERNS = [
    re.compile(r"했다\.$"),
    re.compile(r"이다\.$"),
    re.compile(r"됐다\.$"),
    re.compile(r"한다\.$"),
    re.compile(r"해보자\.$"),
    re.compile(r"하자\.$"),
]


@dataclass
class ScoredDoc:
    doc_id: str
    text: str
    score: float


def _jaccard_similarity(a: str, b: str) -> float:
    """실제 임베딩 코사인 유사도 대신 사용하는 목 유사도(단어 집합 자카드)."""
    words_a = set(WORD_RE.findall(a.lower()))
    words_b = set(WORD_RE.findall(b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def select_fewshot_examples(
    target_text: str,
    corpus: list[tuple[str, str]],
    exclude_ids: set[str],
    top_n: int = 3,
    dedup_threshold: float = 0.6,
) -> list[ScoredDoc]:
    """corpus에서 target_text와 유사한 few-shot 예시를 위생 규칙을 적용해 뽑는다.

    corpus: (doc_id, text) 튜플 리스트.
    exclude_ids: 자기 자신이거나 주제가 동일해 제외할 doc_id 집합.
    dedup_threshold: 이미 선택된 예시와 이 값 이상 유사하면 중복으로 보고 건너뛴다.
    """
    candidates = [
        ScoredDoc(doc_id=doc_id, text=text, score=_jaccard_similarity(target_text, text))
        for doc_id, text in corpus
        if doc_id not in exclude_ids
    ]
    candidates.sort(key=lambda d: d.score, reverse=True)

    selected: list[ScoredDoc] = []
    for cand in candidates:
        if len(selected) >= top_n:
            break
        is_duplicate = any(
            _jaccard_similarity(cand.text, chosen.text) >= dedup_threshold
            for chosen in selected
        )
        if is_duplicate:
            logger.info("중복으로 제외: %s (기존 선택과 유사도 %.2f 이상)", cand.doc_id, dedup_threshold)
            continue
        selected.append(cand)

    logger.info(
        "few-shot 선택 완료: 후보 %d개 중 %d개 (제외 %d개)",
        len(candidates), len(selected), len(exclude_ids),
    )
    return selected


def extract_style_stats(texts: list[str]) -> dict[str, float]:
    """문체 통계(평균 문장 길이, 어미 패턴 분포)를 추출한다."""
    all_sentences = []
    for text in texts:
        all_sentences.extend(s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip())

    if not all_sentences:
        return {"avg_sentence_len": 0.0}

    lengths = [len(WORD_RE.findall(s)) for s in all_sentences]
    avg_len = sum(lengths) / len(lengths)

    ending_counts = {}
    for pattern in ENDING_PATTERNS:
        label = pattern.pattern.replace(r"\.$", "")
        ending_counts[label] = sum(1 for s in all_sentences if pattern.search(s))

    stats = {"avg_sentence_len": round(avg_len, 2), "sentence_count": len(all_sentences)}
    stats.update({f"ending_{k}": v for k, v in ending_counts.items()})
    return stats


if __name__ == "__main__":
    corpus = [
        ("post-1", "LLM 컨텍스트를 압축해 비용을 줄였다. 문서를 문장 단위로 나눠 중요도를 계산했다."),
        ("post-2", "웹 검색 없이 그라운딩을 붙였다. DuckDuckGo HTML을 파싱해 결과를 얻었다."),
        ("post-3", "LLM 컨텍스트 압축을 다른 방식으로 시도했다. 문장 단위 중요도 계산은 동일했다."),
        ("post-4", "오늘 기분이 어땠는지 회고해보자. 체력 관리가 부족했다고 느꼈다."),
    ]

    target = "few-shot 예시로 문체를 재현하는 파이프라인을 만들었다. 자기 참조 문서는 제외해야 한다."

    print("=== few-shot 선택 (post-1 자기 참조 제외 가정) ===")
    selected = select_fewshot_examples(target, corpus, exclude_ids={"post-1"}, top_n=3)
    for doc in selected:
        print(f"{doc.doc_id} (score={doc.score:.2f}): {doc.text[:30]}...")

    print("\n=== 문체 통계 ===")
    stats = extract_style_stats([text for _, text in corpus])
    print(stats)
