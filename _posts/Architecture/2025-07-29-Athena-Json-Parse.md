---
title: Athena JSON 파싱 및 정규식 처리 성능 비교
description:
author:
date: 2025-07-29 00:00:00+00:00
categories: ['Architecture']
tags: ['Architecture', 'AWS', 'Athena']
pin: false
math: false
mermaid: false
---
# Athena JSON 파싱 및 정규식 처리 성능 비교

# 1. Athena 파싱 함수 요약

| 함수 | 설명 | 예시 |
| --- | --- | --- |
| `json_parse(string)` | 문자열을 JSON 객체로 변환 | `json_parse('{"a":1}')` |
| `json_extract(json, path)` | JSON 객체에서 경로로 하위 객체 추출 | `json_extract(json, '$.a')` |
| `json_extract_scalar(json, path)` | JSON 객체에서 경로로 문자열 추출 | `json_extract_scalar(json, '$.a')` |
| `regexp_extract(string, pattern, group)` | 패턴과 그룹 인덱스로 첫 번째 매칭 추출 | `regexp_extract('x:1', 'x:(\\d+)', 1)` |
| `regexp_extract_all(string, pattern, group)` | 패턴과 그룹 인덱스로 **모든 매칭값 배열** 추출 | `regexp_extract_all('x:1,y:2', '(\\d+)', 1)` |

---

## 2. 샘플 JSON 데이터

Athena의 `journey_json` 컬럼에 다음과 같은 JSON 문자열이 포함되어 있습니다.

```json
[
  {
    "dept_airport": "ICN",
    "arr_airport": "NRT",
    "airline": "KE",
    "booking_class": "Y",
    "cabin_class": "Economy"
  },
  {
    "dept_airport": "NRT",
    "arr_airport": "SFO",
    "airline": "KE",
    "booking_class": "J",
    "cabin_class": "Business"
  }
]

```

---

## 3. 세 가지 쿼리 버전 요약

| 버전 | 설명 |
| --- | --- |
| **최초 쿼리** | `regexp_extract_all` + `zip`으로 다항목 파싱 |
| **JSON 파싱 쿼리** | `json_parse` + `UNNEST` + `json_extract_scalar` |
| **최적화된 정규식 쿼리** | 정규식 개선 (`\s*`, `[^"]+`) 등 최적화 |

---

## 4. 각 쿼리 실행 예시 및 결과

### 4.1 최초 쿼리 (`regexp_extract_all` + `zip`)

```sql
WITH base_data AS (
  SELECT
    array_distinct(CAST(zip(
      regexp_extract_all(journey_json, '"dept_airport":\\s*"([^"]*)"', 1),
      regexp_extract_all(journey_json, '"arr_airport":\\s*"([^"]*)"', 1),
      regexp_extract_all(journey_json, '"airline":\\s*"([^"]*)"', 1),
      regexp_extract_all(journey_json, '"booking_class":\\s*"([^"]*)"', 1),
      regexp_extract_all(journey_json, '"cabin_class":\\s*"([^"]*)"', 1)
    ) AS ARRAY(ROW(...))) ) AS journey
  FROM ...
)
SELECT * FROM base_data CROSS JOIN UNNEST(journey) AS t(item);

```

**실행 결과**: 약 300만건의 row, 최대 300건의 Json Array 형태의 데이터

- 실행 시간: 23.635초
- 데이터 스캔: 9.18GB
- zip 인덱스 불일치 시 파싱 오류 가능

---

### 4.2 JSON 파싱 기반 쿼리

```sql
WITH base_data AS (
  SELECT
    CAST(json_parse(journey_json) AS ARRAY(JSON)) AS journey_array
  FROM ...
),
unnested_data AS (
  SELECT
    json_extract_scalar(journey, '$.dept_airport') AS dept_airport,
    json_extract_scalar(journey, '$.arr_airport') AS arr_airport,
    ...
  FROM base_data
  CROSS JOIN UNNEST(journey_array) AS t(journey)
)
SELECT DISTINCT * FROM unnested_data;

```

**실행 결과**: 약 300만건의 row, 최대 300건의 Json Array 형태의 데이터

- 실행 시간: 21.712초
- 데이터 스캔: 9.18GB
- 구조 확장, 유지보수 유리

---

### 4.3 최적화된 정규식 쿼리

```sql
WITH base_data AS (
  SELECT
    CAST(zip(
      regexp_extract_all(journey_json, '"dept_airport"\\s*:\\s*"([^"]+)"', 1),
      ...
    ) AS ARRAY(ROW(...))) AS journey
  FROM ...
)
SELECT * FROM base_data CROSS JOIN UNNEST(journey) AS t(item);

```

**실행 결과**: 약 300만건의 row, 최대 300건의 Json Array 형태의 데이터

- 실행 시간: 20.239초
- 데이터 스캔: 9.18GB
- 기존 방식 유지하며 정규식 단순화

---

## 5. 전체 기능 및 성능 비교표

| 항목 | 최초 쿼리(정규식 + zip) | 두 번째 쿼리(JSON 파싱 기반) | 마지막 쿼리(정규식 최적화) |
| --- | --- | --- | --- |
| **파싱 방식** | `regexp_extract_all` + `zip` | `json_parse` + `UNNEST` + `json_extract_scalar` | `regexp_extract_all` 최적화 (간소화된 정규식) |
| **공백 대응** | 있음 (`\s*`) | JSON 파서 자동 처리 | 최소한의 `\s*` |
| **유지보수성** | 낮음 (정규식 수정 어려움) | 높음 (JSON path만 변경) | 중간 (정규식 유지하지만 간단해짐) |
| **성능 (소규모)** | 빠름 또는 비슷 | 약간 느릴 수 있음 | 빠름 |
| **성능 (대용량)** | 느려질 수 있음 (정규식 부하) | 안정적 (JSON 파싱 최적화) | 상대적으로 빠름 (정규식 간소화) |
| **데이터 유효성** | 일부 누락 가능성 (필드 미정렬 시) | 유효성 높음 (구조적 처리) | 동일 위험 존재 |
| **중첩 JSON 확장성** | 낮음 (추가 정규식 필요) | 매우 좋음 (필드만 추가하면 됨) | 낮음 (정규식 또 추가) |
| **스캔 데이터량** | 9.18 GB | 9.18 GB | 9.18 GB *(동일 조건)* |

---

## 6. 결론 및 추천 시나리오

| 상황 | 추천 쿼리 | 이유 |
| --- | --- | --- |
| 기존 운영 쿼리를 그대로 유지하되 속도만 개선하고 싶다 | **정규식 최적화 버전** | 구조 변경 없이 빠르게 정리 가능 |
| 신규 개발, 복잡한 JSON 구조를 계속 확장할 필요가 있다 | **JSON 파싱 버전** | 유지보수 용이 + 구조적 확장성 |
| 정합성, 정확도보다 빠른 결과가 더 중요하다 (예: 대시보드 조회용) | **최초 또는 정규식 최적화 버전** | 빠르게 결과 확인 가능 |
