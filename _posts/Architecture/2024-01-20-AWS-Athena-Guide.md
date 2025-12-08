---
title: AWS Athena 가이드
description:
author:
date: 2024-01-20 00:00:00+00:00
categories: ['Architecture']
tags: ['Architecture', 'AWS', 'Athena']
pin: false
math: false
mermaid: false
---
# **AWS Athena**

## **AWS Athena란**

- Amazon Web Services(AWS)의 대화형 쿼리 서비스로, 표준 SQL을 사용하여 Amazon S3에 저장된 대규모 데이터를 쉽게 분석할 수 있는 서비스. Athena는 서버리스 아키텍처를 기반으로 하여 확장성이 뛰어남.

## **테이블 최적화 방법**

### **Partitioning과 Bucketing**

- Partitioning 테이블을 분할하여 관리하는 방법
    - 일반적으로 날짜 단위를 사용
- Bucketing 테이블의 특정 키 기반으로 분리하여 처리하는 방법
    - 키 기반 정렬 및 검색에 용이
- Index는 지원하지 않음

### **Flattening**

- Flat 중첩 데이터를 풀어 테이블을 flat하게 변환하는 방법
    - 구조의 개별 항목을 사용하는 json 및 struct 구조에서 활용 가능
    - 중첩 데이터 안의 불필요 데이터가 많을 경우 성능 개선의 효과가 있음
    - 예) `SELECT id, data.name FROM dataset.table CROSS JOIN UNNEST(data) AS t(data)`

### **Pivoting**

- 행과 열을 바꿔 구성하는 방법
    - 동일 행이 중복되거나 행이 key, value형태일 때 활용 가능
    - 대체적으로 열 검색이 빨라 성능 개선 효과가 있음
    - 불필요 열이 많아질 수 있으므로 주의가 필요함
    - 예) `SELECT id, MAX(CASE WHEN key = 'name' THEN value END) AS name FROM dataset.table CROSS JOIN UNNEST(data) AS t(key, value) GROUP BY id`

## **쿼리 속도 개선 방법**

- `SELECT *` 사용 자제
- Partitioned 또는 Bucketed 열을 필수적으로 쿼리에 포함
- WITH 절 사용 권장
    - WITH 절을 사용하여 데이터를 한정하면 속도가 개선됩니다.
- 윈도우 함수 사용 권장
    - 전체 데이터를 ORDER BY 처리하는 것보다 RANK()등 윈도우 함수를 쓰는 것이 더 효율적입니다.
- LIMIT 절 활용
    - 테스트 또는 rank를 처리할 경우 LIMIT 절을 사용하는 것이 좋습니다.
- 쿼리 성능 모니터링 활용
    - Athena 콘솔에서 쿼리 실행 통계를 확인하여 쿼리 성능을 모니터링합니다.
- 쿼리 결과 캐싱
    - Athena의 쿼리 결과는 버킷에 csv파일로 저장되어 캐싱됩니다. 하지만 변하지 않는 데이터의 경우 파일로 캐싱하는 것이 훨씬 효율적입니다.
    - **주의** CTAS를 활용할 경우 별도의 테이블을 만들어 처리하므로 버킷에 캐싱되지 않습니다.

## **제약 사항**

- Athena는 DML 쿼리의 런타임을 30분으로, DDL 쿼리의 런타임을 600분으로 제한
- 메모리가 부족해도 자동 취소됨
- 입력된 데이터 형태가 맞지 않는 경우 오류
- Amazon S3는 요청 수를 초당 5,500개로 제한

## **참고**

- 파티셔닝 및 버킷팅 [분할 및 버킷팅 사용 - Amazon Athena](https://docs.aws.amazon.com/ko_kr/athena/latest/ug/ctas-partitioning-and-bucketing.html)
- 성능 튜닝 [Athena 성능 최적화 - Amazon Athena](https://docs.aws.amazon.com/ko_kr/athena/latest/ug/performance-tuning.html)
- Amazon Athena를 위한 10가지 성능 조정 팁 [Top 10 Performance Tuning Tips for Amazon Athena](https://aws.amazon.com/ko/blogs/big-data/top-10-performance-tuning-tips-for-amazon-athena/)
    
