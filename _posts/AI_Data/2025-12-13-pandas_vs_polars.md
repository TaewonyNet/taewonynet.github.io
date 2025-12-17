---
title: pandas vs polars
description: pandas와 polars가 실제 얼마나 차이나는지 정량적으로 평가하기 위한 벤치마크 테스트한다.
author: taewony
date: 2025-12-13 22:28:00 +0900
categories: [Development,AI/Data]
tags: [pandas,polars,benchmark,dataframe,performance]
pin: false
math: false
mermaid: false
---

## pandas vs polars
pandas와 polars가 실제 얼마나 차이나는지 정량적으로 평가하기 위한 벤치마크 테스트한다.

### 1. 서론 (Introduction)
- **문제/상황 (Problem):**
    - polars가 버전업이 되면서 실제 사용 가능한 수준으로 올라갔다고 한다.
    - 실제 pandas와 비교하여 성능이 얼마나 차이가 나는지 실제 데이터가 동일하게 나오는지 정량적 분석이 필요하다.
- **목적 (Purpose):**
    - 동일 조건에서 pandas와 polars의 연산을 비교하여 실무 적용을 위한 기준을 확보한다.
- **대상 (Target Audience):**
    - spark를 사용하기에는 아쉽고 pandas를 사용하기엔 너무 느린다는 대부분의 사용자.

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - pandas도 옛날에 비해서 성능이 많이 좋아졌으나 python이라는 구조적 한계로 확장이 어렵다고 확인되었다.
    - polars는 rust기반으로 lazy(지연실행) 모델을 사용, 10~100배가 더 빠르다는 소개를 확인하였으며 실제 성능의 정도를 확인하도록 한다.
- **접근 방법 (Approach Methods):**
    - **방법 1:** pandas와 polars의 동일 연산을 각각 독립된 프로세스에서 실행하여 시간과 메모리를 측정한다.
    - **방법 2:** polars의 eager 모드와 lazy 모드를 분리하여 즉시 실행하는 방식과 지연실행하는 방식의 성능을 비교한다.
    - **방법 3:** 순수한 성능 비교를 위해 각각의 thread개수를 1개만 사용하도록 한정하여 절대적으로 비교 가능하게 한다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, Pandas, Polars, Parquet, Multiprocessing
    - **주요 단계:** 데이터 생성 → 연산 실행 → 시간·메모리 측정 → 반복 실행 평균화
    - **결과 도출 및 검증:** 동일 연산을 3회 반복하여 평균값을 사용하고, 프로세스 단위 측정으로 외부 요인의 영향을 최소화한다.

### 3. 결과 (Results)
- **분석 결과 요약:**
    - pandas와 polars eager 모드는 성능의 큰 차이를 보이지 않았다. 메모리 역시 큰 차이를 보이지 않았다.
    - polars lazy 모드는 메모리 사용량이 큰 차이를 보이지 않았으나 속도는 압도적인 압도적으로 빨랐다.
    - polars eager 에서 threads 제약을 풀면 조금 더 빨라지나 pandas와 큰 차이를 보이지 않았다.
```
 === System Info ===
                     0
CPU             x86_64
OS               Linux
Python         3.10.12
Python_pandas    1.5.2
Python_polars   1.27.0
```
=== Comparative Benchmark Summary ===
| Test                          |   Time(s) |   Memory(bytes) | Error   |
|:------------------------------|----------:|----------------:|:--------|
| Pandas GroupBy (1000000)      |  0.1593   |          502613 |         |
| Polars GroupBy (1000000)      |  0.233182 |          449229 |         |
| Polars Lazy GroupBy (1000000) |  0.007997 |          683968 |         |
| Pandas GroupBy (5000000)      |  0.8523   |         2264788 |         |
| Polars GroupBy (5000000)      |  1.1536   |         1677721 |         |
| Polars Lazy GroupBy (5000000) |  0.024379 |         2454440 |         |
| Pandas Join (1000000)         |  0.441    |          714013 |         |
| Polars Join (1000000)         |  0.454117 |          660100 |         |
| Polars Lazy Join (1000000)    |  0.046039 |          752140 |         |
| Pandas Join (5000000)         |  3.3497   |         3249977 |         |
| Polars Join (5000000)         |  2.33583  |         2454440 |         |
| Polars Lazy Join (5000000)    |  0.216409 |         2487541 |         |
| Pandas Filter (1000000)       |  0.1716   |          502770 |         |
| Polars Filter (1000000)       |  0.22309  |          683968 |         |
| Polars Lazy Filter (1000000)  |  0.013805 |          683968 |         |
| Pandas Filter (5000000)       |  0.8276   |         2264857 |         |
| Polars Filter (5000000)       |  1.10919  |         2454440 |         |
| Polars Lazy Filter (5000000)  |  0.029735 |         2454440 |         |
| Pandas Sort (1000000)         |  0.2371   |          502765 |         |
| Polars Sort (1000000)         |  0.281238 |          683968 |         |
| Polars Lazy Sort (1000000)    |  0.048196 |          683968 |         |
| Pandas Sort (5000000)         |  1.4405   |         2264881 |         |
| Polars Sort (5000000)         |  1.49336  |         2454440 |         |
| Polars Lazy Sort (5000000)    |  0.21576  |         2454440 |         |
| Pandas Window (1000000)       |  0.1629   |          502212 |         |
| Polars Window (1000000)       |  0.244593 |          683968 |         |
| Pandas Window (5000000)       |  0.8818   |         2264709 |         |
| Polars Window (5000000)       |  1.20285  |         2454440 |         |


### 4. 인사이트 및 액션 (Insights & Action)
- **인사이트 (Insight):**
    - 대규모 파이프라인 구축 시 pandas보다 polars lazy가 압도적으로 유리하며 lazy를 사용하지 않으면 사실상 의미가 없는 것으로 보인다.
- **실행 방안 (Action Plan):**
    - 파이프라인에서 pandas를 polars를 전환했으나 속도가 개선되지 않는 결과를 확인했는데 lazy모드를 사용하지 않은 것으로 학인하였다.
    - 실제로 실무에서 사용하고 있는 pandas를 polars lazy로 전환한다.
- **한 줄 결론 (Key Takeaway):**
    - 알려진 사실이 실제와 다를 수 있다. 객관적 성능 비교는 늘 필요하다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/pandas_vs_polars.py)
    - 이제 데이터 처리는 polars lazy는 필수로 사용해야한다.
- **다음 스텝 (Next Step):**
    - 실무 데이터 셋을 polars lazy로 전환한다. 추가로 spark도 검증해본다.
