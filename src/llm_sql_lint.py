"""LLM이 생성한 SQL을 실행 전에 정규식 기반으로 정적 검사한다 (FAIL/WARN/OK 3단계)."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

DML_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b", re.IGNORECASE
)
SELECT_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
LIMIT_PATTERN = re.compile(r"\bLIMIT\s+\d+", re.IGNORECASE)


def lint_sql(sql: str) -> tuple[str, str | None]:
    """
    SQL 문자열을 검사해 ("FAIL"|"WARN"|"OK", reason)을 반환한다.

    1) DML/DDL 키워드(INSERT/UPDATE/DELETE/DROP/CREATE/ALTER/TRUNCATE) 검출 시 FAIL
    2) 세미콜론이 2개 이상이면 멀티스테이트먼트로 간주해 FAIL
    3) SELECT인데 LIMIT 절이 없으면 WARN
    위에 걸리지 않으면 OK.
    """
    stripped = sql.strip()

    if DML_PATTERN.search(stripped):
        return "FAIL", "DML/DDL 키워드가 포함됨 (INSERT/UPDATE/DELETE/DROP 등)"

    if stripped.count(";") >= 2:
        return "FAIL", "세미콜론 2개 이상 — 멀티스테이트먼트로 의심됨"

    if SELECT_PATTERN.search(stripped) and not LIMIT_PATTERN.search(stripped):
        return "WARN", "SELECT 쿼리에 LIMIT 절이 없음 (풀 스캔 위험)"

    return "OK", None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    samples = {
        "정상 SELECT+LIMIT": "SELECT id, name FROM users LIMIT 10;",
        "LIMIT 없는 SELECT": "SELECT id, name FROM users WHERE active = 1",
        "DELETE 포함": "DELETE FROM orders WHERE id = 42;",
        "멀티스테이트먼트": "SELECT 1; DROP TABLE users; SELECT 2;",
    }

    for label, sql in samples.items():
        status, reason = lint_sql(sql)
        print(f"[{label}] -> {status} ({reason})")
