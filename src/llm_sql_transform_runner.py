#!/usr/bin/env python3
"""LLM이 생성한 변환 함수를 dbt의 schema.yml처럼 계약(contract)으로 검증 후 실행한다.

`transform_fn`을 실행한 결과 DataFrame을 `schema` 딕셔너리(컬럼명 -> 타입/제약)와
대조해 컬럼 누락·타입 불일치·not-null 위반이 있으면 예외를 던지고, 통과한
경우에만 결과를 반환한다. 계약 검증 없이 LLM 생성 코드의 출력을 그대로 쓰면
스키마가 조용히 깨질 수 있다는 문제를 막기 위한 최소 게이트다.

requirements: pandas (Polars가 없는 환경을 고려해 pandas로 최소 구현했다.
실제로는 Polars DataFrame에도 동일한 계약 검증 로직을 그대로 적용할 수 있다.)
"""
from __future__ import annotations

import logging
from typing import Any, Callable

import pandas as pd

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_TYPE_CHECKS: dict[str, Callable[[pd.Series], bool]] = {
    "int": lambda s: pd.api.types.is_integer_dtype(s),
    "float": lambda s: pd.api.types.is_float_dtype(s) or pd.api.types.is_integer_dtype(s),
    "date": lambda s: pd.api.types.is_datetime64_any_dtype(s),
    "str": lambda s: pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s),
    "bool": lambda s: pd.api.types.is_bool_dtype(s),
}


class ContractViolation(Exception):
    """계약(schema) 위반 시 발생하는 예외."""


def _validate_contract(df: pd.DataFrame, schema: dict[str, dict[str, Any]]) -> list[str]:
    """DataFrame을 schema와 대조해 위반 사항 리스트를 반환한다(빈 리스트면 통과)."""
    violations: list[str] = []

    for col, rule in schema.items():
        if col not in df.columns:
            violations.append(f"컬럼 누락: {col}")
            continue

        series = df[col]

        expected_type = rule.get("type")
        if expected_type:
            checker = _TYPE_CHECKS.get(expected_type)
            if checker is None:
                violations.append(f"{col}: 알 수 없는 타입 규칙 {expected_type!r}")
            elif not checker(series):
                violations.append(f"{col}: 타입 불일치 (기대={expected_type}, 실제={series.dtype})")

        if rule.get("not_null") and series.isnull().any():
            null_count = int(series.isnull().sum())
            violations.append(f"{col}: not-null 위반 ({null_count}건 결측)")

        if "min" in rule:
            numeric = pd.to_numeric(series, errors="coerce")
            below = numeric < rule["min"]
            if below.any():
                violations.append(f"{col}: min({rule['min']}) 미만 값 {int(below.sum())}건")

    return violations


def run_with_contract(
    transform_fn: Callable[[pd.DataFrame], pd.DataFrame],
    df: pd.DataFrame,
    schema: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    """변환 함수를 실행하고 결과를 schema와 대조 검증한 뒤에만 반환한다.

    schema 예시: {"revenue": {"type": "float", "not_null": True, "min": 0}}
    위반이 하나라도 있으면 ContractViolation을 던지고 결과는 반환하지 않는다.
    """
    result = transform_fn(df)
    violations = _validate_contract(result, schema)

    if violations:
        logger.error("계약 위반 %d건: %s", len(violations), violations)
        raise ContractViolation(f"schema 계약 위반 {len(violations)}건: {violations}")

    logger.info("계약 검증 통과: 컬럼 %d개, 행 %d개", len(result.columns), len(result))
    return result


if __name__ == "__main__":
    raw = pd.DataFrame(
        {
            "month": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]),
            "revenue_raw": [1000, 2000, 3000],
        }
    )

    schema = {
        "month": {"type": "date", "not_null": True},
        "revenue": {"type": "float", "not_null": True, "min": 0},
    }

    def good_transform(df: pd.DataFrame) -> pd.DataFrame:
        """LLM이 만들었다고 가정하는, 계약을 지키는 변환."""
        out = df.copy()
        out["revenue"] = out["revenue_raw"].astype(float)
        return out[["month", "revenue"]]

    def bad_transform(df: pd.DataFrame) -> pd.DataFrame:
        """LLM이 만들었다고 가정하는, 컬럼명을 잘못 지은 변환(계약 위반 유도)."""
        out = df.copy()
        out["sales"] = out["revenue_raw"].astype(float)  # 'revenue'가 아니라 'sales'
        return out[["month", "sales"]]

    print("=== 계약을 지키는 변환 ===")
    ok_result = run_with_contract(good_transform, raw, schema)
    print(ok_result)

    print("\n=== 계약을 위반하는 변환 ===")
    try:
        run_with_contract(bad_transform, raw, schema)
    except ContractViolation as exc:
        print(f"차단됨: {exc}")
