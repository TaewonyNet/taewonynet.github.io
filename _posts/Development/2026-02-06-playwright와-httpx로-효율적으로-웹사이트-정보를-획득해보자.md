---
title: playwright와 httpx로 효율적으로 웹사이트 정보를 획득해보자
description: playwright를 사용하되 데이터를 httpx를 사용하도록 하이브리드형 클라이언트를 만들자
author: taewony
date: 2026-02-06 21:09:47 +0900
categories: [Development, Tech/Architecture]
tags: [python, playwright, httpx, hybrid-client, web-scraping, automation, performance-optimization]
pin: false
math: false
mermaid: false
---

## playwright와 httpx로 효율적으로 웹사이트 정보를 획득해보자
playwright를 사용하되 데이터를 httpx를 사용하도록 하이브리드형 클라이언트를 만들자

### 1. 서론 (Introduction)

- **문제/상황 (Problem):**
    - 브라우저 자동화 도구(Playwright)는 모든 동적 요소를 처리할 수 있지만 리소스 소모가 크고 느리며, 단순 HTTP 요청(httpx)은 빠르지만 로그인이나 봇 우회가 어렵다는 상충된 문제가 있다.
- **목적 (Purpose):**
    - Playwright로 복잡한 로그인과 보안 통과를 수행한 후 쿠키를 추출하여 httpx에 이식하는 '하이브리드' 방식의 고효율 크롤링 클라이언트를 구축한다.
- **대상 (Target Audience):**
    - 보안이 강화된 사이트에서 대규모 데이터를 빠르게 수집해야 하는 성능 지향적 데이터 엔지니어

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - 브라우저 세션의 쿠키 구조와 httpx의 쿠키 저장소(CookieJar) 간의 호환성을 검증하였다.

| 기능                       | 설명                                      | 장점                                   |
| -------------------------- | ----------------------------------------- | -------------------------------------- |
| **쿠키 덤프(Cookie Dump)** | 브라우저 컨텍스트의 쿠키를 추출           | 로그인 상태의 핵심 증표를 안전하게 획득 |
| **쿠키 주입(Cookie Injection)** | 추출된 쿠키를 httpx 클라이언트에 설정     | 브라우저 없이도 인증된 요청 수행 가능  |
| **하이브리드 워크플로우**  | 인증은 브라우저로, 수집은 HTTP 클라이언트로 | 보안 통과와 고속 수집의 장점만 결합   |
| **가상 화면 활용**         | 로그인 시에만 가상 화면 브라우저 사용     | 전체 프로세스의 리소스 사용량 최소화   |
| **비동기 통합**            | 두 라이브러리 모두 asyncio 기반으로 연동  | 코드 일관성 유지 및 논블로킹 처리      |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** 가상 화면 환경에서 Playwright를 Headed 모드로 실행하여 수동 또는 자동 로그인을 완벽하게 수행한다.
    - **[방법 2]:** context.cookies()를 통해 획득한 세션 정보를 httpx.AsyncClient의 쿠키 저장소에 동기화한다.

- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, playwright, httpx, pyvirtualdisplay, beautifulsoup4
    - **주요 단계:** 하이브리드 WebClient 설계 $\rightarrow$ Playwright 로그인 및 쿠키 추출 로직 구현 $\rightarrow$ httpx 쿠키 주입 엔진 개발 $\rightarrow$ 추출된 세션을 이용한 고속 메타 데이터 수집 $\rightarrow$ 전체 자원 관리 최적화
    - **결과 도출 및 검증:** 브라우저만 사용했을 때보다 수집 속도가 수십 배 이상 향상되면서도, 로그인 상태가 완벽히 유지됨을 확인한다.

### 3. 결과 (Results)

- **분석 결과 요약:**
    - 하이브리드 방식은 브라우저의 강력한 우회 능력과 HTTP 클라이언트의 압도적인 속도를 동시에 제공함을 증명하였다.
    - 특히 대량의 페이지를 크롤링할 때 브라우저 인스턴스 오버헤드를 제거함으로써 서버 리소스를 극도로 효율적으로 활용할 수 있었다.

### 4. 인사이트 및 액션 (Insights & Action)

- **인사이트 (Insight):**
    - 화면이 존재하고 로그인할 수 있으며 해당 데이터를 별도로 추출할 수 있는 클라이언트를 만들었다. 크롤링에 활용해보자.
    - 기술의 장단점을 파악하고 이를 결합하는 아키텍처 설계가 복잡한 문제를 해결하는 가장 강력한 무기이다.
- **실행 방안 (Action Plan):**
    - 현재 운영 중인 모든 대규모 크롤링 파이프라인에 하이브리드 클라이언트를 표준 엔진으로 이식한다.
- **한 줄 결론 (Key Takeaway):**
    - Playwright와 httpx의 하이브리드 전략으로 보안과 성능이라는 두 마리 토끼를 모두 잡을 수 있다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/webclient_hv.py){: target="_blank"}
- **다음 스텝 (Next Step):**
    - 분산 노드 환경에서 하이브리드 클라이언트를 배포하여 전 세계적인 데이터 수집 망을 구축한다.
