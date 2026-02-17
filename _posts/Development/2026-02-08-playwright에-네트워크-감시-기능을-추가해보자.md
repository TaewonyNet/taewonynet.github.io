---
title: playwright에 네트워크 감시 기능을 추가해보자
description: playwright에 har형식으로 네트워크를 감시하여 필요한 데이터를 획득해보자
author: taewony
date: 2026-02-08 22:15:30 +0900
categories: [Development, Tech/Architecture]
tags: [python, playwright, har, network-monitoring, web-scraping, automation, httpx]
pin: false
math: false
mermaid: false
---

## playwright에 네트워크 감시 기능을 추가해보자
playwright에 har형식으로 네트워크를 감시하여 필요한 데이터를 획득해보자

### 1. 서론 (Introduction)

- **문제/상황 (Problem):**
    - 단순히 HTML을 크롤링하는 것만으로는 동적으로 비동기 호출(API)되는 데이터나 복잡한 리소스를 추적하기에 한계가 있다.
- **목적 (Purpose):**
    - Playwright의 HAR(HTTP Archive) 레코딩 기능을 활용하여 모든 네트워크 통신을 기록하고 이를 통해 필요한 API 데이터를 정밀하게 획득한다.
- **대상 (Target Audience):**
    - 복잡한 API 통신 구조를 가진 웹사이트에서 핵심 데이터를 누락 없이 수집하고자 하는 백엔드 및 데이터 엔지니어

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - 브라우저의 모든 네트워크 트랜잭션을 표준화된 JSON 형태인 HAR 파일로 저장하고 분석하는 메커니즘을 검증하였다.

| 기능                       | 설명                                      | 장점                                   |
| -------------------------- | ----------------------------------------- | -------------------------------------- |
| **HAR 레코딩**             | 모든 HTTP 요청과 응답을 파일로 기록       | 누락 없는 데이터 흐름 추적 및 재현 가능 |
| **트랜잭션 분석**          | HAR 파일을 JSON으로 파싱하여 특정 패턴 검색 | 필요한 API 엔드포인트와 헤더를 정확히 식별 |
| **요청 재현 (Replay)**     | 기록된 헤더를 복제하여 httpx로 재요청     | 브라우저 없이도 인증된 API 데이터 재획득 가능 |
| **메모리 적재**            | 획득한 바이너리 데이터를 직접 메모리에 적재 | 디스크 I/O 없이 대량의 리소스를 고속 처리 |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** `record_har_path` 옵션을 사용하여 브라우저 세션 중 발생하는 모든 네트워크 활동을 파일로 덤프한다.
    - **[방법 2]:** 저장된 HAR 파일에서 URL 패턴 매칭을 통해 관심 있는 API 요청의 헤더와 메소드를 추출하고 httpx로 재실행한다.

- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, playwright, httpx, json, re
    - **주요 단계:** HAR 레코딩 설정 $\rightarrow$ 브라우저 자동화 및 통신 기록 $\rightarrow$ HAR 파일 파싱 및 데이터 필터링 $\rightarrow$ httpx 기반 요청 재현 및 바이너리 획득 $\rightarrow$ 수집 데이터 검증
    - **결과 도출 및 검증:** 실제 서비스의 복잡한 API 호출을 HAR로 획득하고, 이를 재현하여 원본 데이터를 완벽하게 복원함을 확인한다.

### 3. 결과 (Results)

- **분석 결과 요약:**
    - 네트워크 감시 기능을 통해 브라우저 화면에 보이지 않는 비가시적 API 데이터를 구조적으로 획득하는 데 성공하였다.
    - 특히 이미지, PDF, JSON 응답 등 다양한 형태의 리소스를 원본 통신 환경을 그대로 유지한 채 확보할 수 있음을 증명하였다.

### 4. 인사이트 및 액션 (Insights & Action)

- **인사이트 (Insight):**
    - 이제 화면 및 네트워크까지 확장하는 클라이언트를 만들었다. api 데이터를 획득해보자.
    - 가시적인 HTML 요소를 넘어 보이지 않는 통신 데이터까지 통제할 수 있을 때 진정한 데이터 수집의 자유가 생긴다.
- **실행 방안 (Action Plan):**
    - API 엔드포인트가 자주 변경되거나 난독화된 사이트에 대해 HAR 기반의 자동 추적 로직을 기본 수집 모듈로 채택한다.
- **한 줄 결론 (Key Takeaway):**
    - Playwright의 HAR 레코딩과 httpx의 재현 기능을 결합하여 가장 정교한 네트워크 데이터 수집기를 완성하자. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/webclient_har.py){: target="_blank"}
- **다음 스텝 (Next Step):**
    - 이제 화면 및 네트워크까지 확장하는 클라이언트를 만들었다. API 데이터를 획득하여 활용해보자.
