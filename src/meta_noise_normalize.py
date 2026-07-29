"""멀티소스 메타데이터의 상태 괄호·기호 노이즈를 조회 시점에 정규화하는 PoC(저장은 원본 그대로)."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# 소스 시스템마다 계정 상태를 이런 식으로 필드에 덧붙인다.
STATUS_SUFFIX_RE = re.compile(
    r"\s*\((?:Deactivated|Unlicensed|퇴사|비활성|휴면)\)\s*", re.IGNORECASE
)

CATEGORY_NOISE_RE = re.compile(r"""^[\s"'#]+|[\s"']+$""")

DOC_TYPE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("회의록", ("회의록", "미팅노트", "meeting notes", "논의사항")),
    ("이슈", ("버그", "이슈", "issue", "장애", "오류")),
    ("가이드", ("가이드", "how-to", "튜토리얼", "매뉴얼", "guide")),
]


def normalize_author(raw: str) -> str:
    """작성자 필드에서 상태 괄호(예: '(Deactivated)')를 제거해 동일 인물을 하나로 합친다."""
    return STATUS_SUFFIX_RE.sub("", raw).strip()


def normalize_category(raw: str) -> str:
    """카테고리 필드에서 따옴표·해시 접두 등 표기 노이즈를 제거한다."""
    cleaned = CATEGORY_NOISE_RE.sub("", raw)
    return cleaned.lstrip("#").strip()


def classify_doc_type(text: str) -> str:
    """키워드 규칙 기반으로 문서 타입을 분류한다. 규칙에 안 걸리면 '미분류'로 남긴다."""
    lowered = text.lower()
    for doc_type, keywords in DOC_TYPE_RULES:
        if any(keyword.lower() in lowered for keyword in keywords):
            return doc_type
    return "미분류"


def fetch_normalized(raw_rows: list[dict]) -> list[dict]:
    """저장은 원본 그대로 두고, 조회 시점에만 정규화를 적용한다(백필 대신 read-time normalize)."""
    normalized = []
    for row in raw_rows:
        normalized.append(
            {
                "author": normalize_author(row["author"]),
                "category": normalize_category(row["category"]),
                "doc_type": classify_doc_type(row["body"]),
                "_raw_author": row["author"],
                "_raw_category": row["category"],
            }
        )
    return normalized


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    # DB에는 이 원본 그대로 저장돼 있다고 가정한다(백필 없음).
    raw_rows = [
        {"author": "김철수 (Deactivated)", "category": "'#인프라'", "body": "이번 주 회의록 정리"},
        {"author": "이영희 (퇴사)", "category": "# 백엔드", "body": "로그인 버그 재현 안 됨"},
        {"author": "김철수", "category": "\"인프라\"", "body": "배포 가이드 how-to 정리"},
        {"author": "박민수 (Unlicensed)", "category": "기타", "body": "다음 분기 아이디어 메모"},
    ]

    print("원본 -> 정규화 (조회 시점 변환):")
    for row, norm in zip(raw_rows, fetch_normalized(raw_rows)):
        print(f"  author  : {row['author']!r:<24} -> {norm['author']!r}")
        print(f"  category: {row['category']!r:<24} -> {norm['category']!r}")
        print(f"  doc_type: {norm['doc_type']}")
        print("  ---")
