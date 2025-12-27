---
title: pandas to polars 
description: pandas를 polars로 변환하는 치트시트를 만들고 해당 내용 검증한다.
author: taewony
date: 2025-12-28 00:00:00 +0900
categories: [Development,AI/Data]
tags: [pandas,polars,cheatsheet,dataframe,migration]
pin: false
math: false
mermaid: false
---

## pandas to polars
pandas를 polars로 변환하는 치트시트를 만들고 해당 내용 검증한다.

### 1. 서론 (Introduction)

- **문제/상황 (Problem):**
    - polars로 lazy mode 사용이 필수로 판단됨에 따라 전환을 시도하려 한다.
- **목적 (Purpose):**
    - 검증된 pandas to polars 변환 치트시트를 제공하여 실무에서 사용 가능하게 한다.
- **대상 (Target Audience):**
    - polars 전환이 필요한 나같은 사람.

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - 기존 사용 함수를 정리하여 google 및 gemini를 이용하여 pandas에서 polars로 전환하는 코드 검색하여 확인한다.

    - 1. 기본 정보 및 입출력 (I/O)

| 기능 | Pandas (1.5.2 ~ 2.0.0) | Polars (>= 1.27.0) |
| --- | --- | --- |
| **임포트** | `import pandas as pd` | `import polars as pl` |
| **DataFrame 생성** | `pd.DataFrame(data)` | `pl.DataFrame(data)` (schema 지정 가능) |
| **CSV 읽기** | `pd.read_csv()` | `pl.read_csv()` (Lazy: `pl.scan_csv()`) |
| **Parquet 읽기** | `pd.read_parquet()` | `pl.read_parquet()` (Lazy: `pl.scan_parquet()`) |
| **CSV 쓰기** | `df.to_csv()` | `df.write_csv()` |
| **Parquet 쓰기** | `df.to_parquet()` | `df.write_parquet()` |
| **상호 변환** | - | `pl.from_pandas(pd_df)` / `df.to_pandas()` |

    - 2. 검사 및 통계

| 기능 | Pandas | Polars |
| --- | --- | --- |
| **크기 (행, 열)** | `df.shape` | `df.shape` |
| **행 수** | `len(df)` | `df.height` 또는 `len(df)` |
| **컬럼 목록** | `df.columns` | `df.columns` |
| **데이터 타입** | `df.dtypes` | `df.schema` |
| **메모리 사용량** | `df.memory_usage(deep=True)` | `df.estimated_size()` (바이트 단위) |
| **통계 요약** | `df.describe()` | `df.describe()` (Polars가 더 상세함) |
| **상위/하위 데이터** | `df.head(5)` / `df.tail(5)` | `df.head(5)` / `df.tail(5)` |
| **고유값 수** | `df.nunique()` | `{col: df[col].n_unique() for col in df.columns}` |

    - 3. 선택 및 조작

| 기능 | Pandas | Polars |
| --- | --- | --- |
| **컬럼 선택** | `df[["a", "b"]]` | `df.select(["a", "b"])` (또는 `cs` 선택자) |
| **컬럼 이름 변경** | `df.rename(columns={...})` | `df.rename({...})` |
| **컬럼 삭제** | `df.drop(columns=[...])` | `df.drop(...)` |
| **행 필터링** | `df[df["a"] > 5]` | `df.filter(pl.col("a") > 5)` |
| **고유 행 추출** | `df.drop_duplicates()` | `df.unique()` |
| **데이터 정렬** | `df.sort_values("col")` | `df.sort("col")` (역순: `descending=True`) |
| **컬럼 추가** | `df.assign(new_col=...)` | `df.with_columns(pl.col(...).alias("new_col"))` |
| **타입 변환** | `df.astype({})` | `df.with_columns(pl.col().cast(pl.Float64))` |
| **결측치 채우기** | `df.fillna()` | `df.fill_null()` (NaN은 `fill_nan()`) |
| **결측치 삭제** | `df.dropna()` | `df.drop_nulls()` |
| **문자열 대체** | `df["col"].str.replace()` | `pl.col().str.replace()` |
| **문자열 분할** | `df["col"].str.split()` | `pl.col().str.split()` |
| **문자열 포함 여부** | `df["col"].str.contains()` | `pl.col().str.contains()` |
| **값 제한 (Clip)** | `df.clip(lower, upper)` | `pl.col().clip(min_val, max_val)` |
| **조건부 선택** | `np.where()` | `pl.when().then().otherwise()` |

    - 4. 그룹화, 집계 및 조인

| 기능 | Pandas | Polars |
| --- | --- | --- |
| **그룹화 집계** | `df.groupby().agg()` | `df.group_by().agg()` |
| **다중 집계** | `df.groupby().agg({"c": ["sum"]})` | `df.group_by().agg([pl.col().sum()])` |
| **윈도우 함수** | `df.groupby()["c"].transform()` | `pl.col().sum().over("key")` |
| **피벗 (Pivot)** | `df.pivot_table()` | `df.pivot(index, columns, values)` |
| **언피벗 (Melt)** | `df.melt()` | `df.unpivot(index, on)` |
| **롤링 평균** | `df["c"].rolling().mean()` | `pl.col().rolling_mean(window_size=3)` |
| **조인 (Join)** | `pd.merge()` | `df1.join(df2)` (anti, semi, cross 지원) |
| **결합 (Concat)** | `pd.concat()` | `pl.concat()` |

    - 5. Lazy API (큰 데이터 처리)

| 기능 | Pandas | Polars (LazyFrame) |
| --- | --- | --- |
| **지연 실행 스캔** | - | `pl.scan_csv()`, `pl.scan_parquet()` |
| **실제 계산 수행** | (즉시 실행) | `lazy_df.collect()` |
| **스트리밍 읽기** | - | `pl.read_csv(..., streaming=True)` |
| **일부 행만 읽기** | `pd.read_csv(nrows=n)` | `pl.scan_csv(...).limit(n).collect()` |
| **Lazy 모드 전환** | - | `df.lazy()` |

    - 6. Polars 선택자 (Selectors)

| 패턴 종류 | 코드 (`import polars.selectors as cs`) |
| --- | --- |
| **숫자형 선택** | `df.select(cs.numeric())` |
| **문자형 선택** | `df.select(cs.string())` |
| **이름 패턴(Regex)** | `df.select(cs.by_name("^col_"))` |
| **특정 컬럼 제외** | `df.select(cs.exclude("col_to_drop"))` |
| **접두사/접미사** | `df.select(cs.starts_with("pre_"), cs.ends_with("_suf"))` |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** 기존 사용하던 pandas의 주요 함수를 모두 추출하고 대상 polars 코드를 찾는다.
    - **[방법 2]:** 치트시트를 만든 후 해당 테스트코드를 만들어 실제 같은 결과를 출력하는지 확인한다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, pandas, polars.
    - **주요 단계:** 코드 분석 $\rightarrow$ 카테고리 정리 $\rightarrow$ 테스트 실행 및 결과 비교.
    - **결과 도출 및 검증:** 치트시트 기반의 테스트 코드가 실제 pandas를 polars로 전환하는 것에 대해 신뢰성을 검증한다.

### 3. 결과 (Results)

- **분석 결과 요약:**
    - 치트시트 기반 테스트 실행 결과 모든 항목에 대한 검증이 모두 완료되었다. 

### 4. 인사이트 및 액션 (Insights & Action)

- **인사이트 (Insight):**
    - polars의 표션식이 pandas보다 일관되며 성능이 좋아 효율적 사용이 가능하다.
- **실행 방안 (Action Plan):**
    - 테스트 코드와 동일 코드를 쓰는 pandas부분을 polars를 사용하는 것으로 바꾼다. 바꾸기전과 후를 비교하여 실제 동일 값인지 재 검증한다.
- **한 줄 결론 (Key Takeaway):**
    - 치트시트로 pandas를 polars로 변경하는 표준을 만들어 활용한다.
- **다음 스텝 (Next Step):**
    - 실제 업무 데이터를 해당 치트시트를 이용해 실행한다.
