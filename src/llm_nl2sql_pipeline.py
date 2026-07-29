"""자연어 질문 -> 도메인 분류 -> 소스(테이블) 선택 -> SQL 생성 3단계 파이프라인 (목 버전)."""
from __future__ import annotations

import logging
import math
from typing import Sequence

logger = logging.getLogger(__name__)

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "sales": ("매출", "판매", "주문"),
    "inventory": ("재고", "입고", "출고"),
    "user": ("가입", "회원", "유저"),
}

DOMAIN_TABLES: dict[str, str] = {
    "sales": "sales_orders",
    "inventory": "inventory_stock",
    "user": "user_accounts",
}


def classify_domain(question: str) -> str:
    """키워드 매칭으로 질문의 도메인을 분류한다. 실제로는 임베딩+벡터검색으로 대체할 수 있다."""
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in question for keyword in keywords):
            return domain
    return "unknown"


def select_source(domain: str) -> str | None:
    """도메인에 매핑된 테이블명을 딕셔너리 조회로 반환한다."""
    return DOMAIN_TABLES.get(domain)


def generate_sql(question: str, table: str) -> str:
    """질문과 선택된 테이블명으로 최소 SELECT 문을 문자열 템플릿으로 생성한다."""
    return f"-- Q: {question}\nSELECT * FROM {table} LIMIT 10;"


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """실제 임베딩 모델 없이 벡터 유사도 개념만 보여주는 목(mock) 함수."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def run_pipeline(question: str) -> str | None:
    """3단계를 순서대로 실행해 최종 SQL 문자열을 반환한다. 도메인 미분류면 None."""
    domain = classify_domain(question)
    table = select_source(domain)
    if table is None:
        logger.warning("도메인을 분류하지 못함: %s", question)
        return None
    return generate_sql(question, table)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    questions = [
        "지난달 매출 상위 10개 보여줘",
        "재고 부족한 상품 알려줘",
        "이번 주 신규 가입 회원 수는",
        "오늘 날씨 어때",  # 미분류 케이스
    ]

    for q in questions:
        sql = run_pipeline(q)
        print(f"[{q}] -> {sql}")

    # 벡터 유사도 목 함수 데모 (실제 임베딩 대신 단순 숫자 벡터)
    sim = cosine_similarity([1.0, 0.0, 1.0], [1.0, 0.0, 0.9])
    print(f"cosine_similarity 예시: {sim:.4f}")
