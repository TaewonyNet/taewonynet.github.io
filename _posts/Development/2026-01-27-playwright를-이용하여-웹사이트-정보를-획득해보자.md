---
title: playwright를 이용하여 웹사이트 정보를 획득해보자
description: playwright로 실제 브라우져에 가깝게 접속하여 데이터를 획득해보자
author: taewony
date: 2026-01-27 21:28:44 +0900
categories: [Development, Tech/Architecture]
tags: [python, playwright, automation, web-scraping, dynamic-content, browser-automation]
pin: false
math: false
mermaid: false
---

## playwright를 이용하여 웹사이트 정보를 획득해보자
playwright로 실제 브라우져에 가깝게 접속하여 데이터를 획득해보자

### 1. 서론 (Introduction)

- **문제/상황 (Problem):**
    - 자바스크립트로 렌더링되는 현대적인 웹사이트들은 단순한 HTTP 요청(requests, httpx)만으로는 전체 콘텐츠를 수집하는 데 한계가 있다.
- **목적 (Purpose):**
    - Playwright를 활용하여 실제 브라우저 환경에서 웹사이트에 접속하고, 동적으로 생성되는 데이터를 완벽하게 획득한다.
- **대상 (Target Audience):**
    - SPA(Single Page Application)나 복잡한 사용자 인터랙션이 포함된 웹사이트를 크롤링해야 하는 개발자

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - 크로스 브라우저 지원과 강력한 자동 대기(Auto-waiting) 기능을 제공하는 Playwright의 엔진 성능을 분석하였다.

| 기능                       | 설명                                      | 장점                                   |
| -------------------------- | ----------------------------------------- | -------------------------------------- |
| **Headless 모드**          | 화면 출력 없는 브라우저 실행              | 리소스 사용 최적화 및 서버 환경 적합   |
| **Auto-waiting**           | 요소가 나타날 때까지 자동 대기            | 복잡한 sleep 로직 없이 안정적 스크래핑 가능 |
| **Browser Context**        | 독립적인 브라우저 세션 관리               | 쿠키 및 로컬 스토리지의 완벽한 격리    |
| **네트워크 상태 대기**     | networkidle 등 로딩 상태 감지             | 비동기 데이터 로드가 완료된 시점 파악 용이 |
| **폼 인터랙션**            | fill, click 등 사용자 행동 모사           | 실제 사용자와 동일한 로그인 프로세스 수행 |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** async_playwright를 통해 비동기적으로 브라우저 인스턴스를 시작하고 페이지 객체를 생성한다.
    - **[방법 2]:** fill과 click 메서드를 사용하여 로그인 폼을 작성하고 제출한 뒤, 네트워크 유휴 상태를 기다린다.

- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, playwright, beautifulsoup4
    - **주요 단계:** playwright 설치 및 브라우저 바이너리 준비 $\rightarrow$ WebClient 클래스 내 브라우저 초기화 로직 구현 $\rightarrow$ 페이지 이동 및 폼 조작 코드 작성 $\rightarrow$ 렌더링된 HTML 소스 추출 $\rightarrow$ 자원 해제를 위한 close 로직 추가
    - **결과 도출 및 검증:** 단순 요청으로는 접근 불가능했던 동적 렌더링 영역의 메타 데이터를 성공적으로 추출함을 확인한다.

### 3. 결과 (Results)

- **분석 결과 요약:**
    - Playwright는 실제 브라우저와 동일한 렌더링 엔진을 사용하므로, 자바스크립트 기반의 복잡한 사이트에서도 정확한 데이터를 수집할 수 있었다.
    - 브라우저 컨텍스트를 활용하여 세션 상태를 유지함으로써 로그인 이후의 보호된 페이지 데이터도 손쉽게 획득 가능함을 확인하였다.

### 4. 인사이트 및 액션 (Insights & Action)

- **인사이트 (Insight):**
    - 실제 웹 사이트에 접속하는 것처럼 데이터를 가져와봤다. 실제 화면이 존재하는 방식으로 수정해서 크롤링을 좀 더 강력하게 해보자.
    - 현대적인 크롤링 아키텍처에서 브라우저 자동화 도구의 도입은 데이터 수집의 완성도를 결정짓는 핵심 요소이다.
- **실행 방안 (Action Plan):**
    - 정적 분석으로 한계가 있는 대상 사이트들에 대해 Playwright 기반의 엔진을 표준으로 채택한다.
- **한 줄 결론 (Key Takeaway):**
    - Playwright를 사용하면 사람과 동일한 방식으로 웹사이트와 상호작용하며 모든 데이터를 획득할 수 있다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/webclient_pw.py){: target="_blank"}
- **다음 스텝 (Next Step):**
    - 봇 감지 우회 및 디버깅 편의성을 위해 가상 화면을 활용한 유저 인터페이스 모드를 탐구한다.
