---
title: playwright에 화면을 달아 웹사이트 정보를 획득해보자
description: playwright를 좀 더 현실적으로 만들기 위해 화면을 달아보자
author: taewony
date: 2026-01-29 22:51:12 +0900
categories: [Development, Tech/Architecture]
tags: [python, playwright, pyvirtualdisplay, automation, web-scraping, browser-automation, virtual-display]
pin: false
math: false
mermaid: false
---

## playwright에 화면을 달아 웹사이트 정보를 획득해보자
playwright를 좀 더 현실적으로 만들기 위해 화면을 달아보자

### 1. 서론 (Introduction)

- **문제/상황 (Problem):**
    - Headless 모드의 브라우저는 리소스 효율적이지만, 일부 웹사이트의 봇 감지 로직에 걸리거나 디버깅 시 실제 렌더링 과정을 확인하기 어렵다.
- **목적 (Purpose):**
    - pyvirtualdisplay를 활용하여 서버 환경에서도 가상 화면(Virtual Display)을 생성하고, 브라우저를 Headed 모드(headless=False)로 실행하여 탐지 우회와 시각적 검증을 동시에 달성한다.
- **대상 (Target Audience):**
    - 봇 감지가 강력한 사이트를 크롤링해야 하거나, GUI가 없는 리눅스 서버 환경에서 브라우저 화면 기반의 자동화를 수행하려는 개발자

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - Xvfb(X Virtual Framebuffer) 기반의 pyvirtualdisplay가 제공하는 가상 디스플레이 환경과 Playwright의 Headed 모드 결합 시의 안정성을 조사하였다.

| 기능                       | 설명                                      | 장점                                   |
| -------------------------- | ----------------------------------------- | -------------------------------------- |
| **가상 화면(Xvfb)**        | 메모리 상에 가상 디스플레이 생성          | 물리 모니터 없이도 GUI 애플리케이션 실행 가능 |
| **Headed 모드 실행**       | 브라우저 UI를 띄운 상태로 동작            | 실제 사용자와 유사한 브라우징 환경 모사 |
| **디스플레이 크기 제어**   | 가상 화면 해상도(예: 1280x720) 설정       | 웹사이트의 반응형 레이아웃 및 렌더링 최적화 |
| **브라우저 컨텍스트 유지** | 세션 및 사용자 에이전트 커스터마이징      | 지능적인 봇 탐지 알고리즘 우회 가능    |
| **리소스 생명주기 관리**   | display.stop()을 통한 자원 정리           | 작업 완료 후 시스템 메모리 및 프로세스 누수 방지 |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** pyvirtualdisplay.Display 객체를 생성하고 시작하여 가상 X 서버 환경을 마련한다.
    - **[방법 2]:** playwright의 launch 옵션에서 headless=False로 설정하여 가상 화면 내에서 실제 브라우저가 동작하게 한다.

- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, playwright, pyvirtualdisplay, beautifulsoup4
    - **주요 단계:** 시스템 내 Xvfb 설치 확인 $\rightarrow$ 가상 화면 시작 로직 구현 $\rightarrow$ Headed 모드로 브라우저 런칭 $\rightarrow$ 실제 화면 렌더링 기반 데이터 추출 $\rightarrow$ 가상 화면 및 브라우저 종료 프로세스 통합
    - **결과 도출 및 검증:** Headless 모드에서 발생할 수 있는 탐지 문제를 우회하고, 가상 화면 상에서 정확한 페이지 로딩과 데이터 획득이 이루어짐을 확인한다.

### 3. 결과 (Results)

- **분석 결과 요약:**
    - 가상 화면을 도입함으로써 서버 환경에서도 실제 사용자의 브라우저 사용 환경을 완벽하게 재현할 수 있었다.
    - Headed 모드로 동작함에 따라 브라우저 고유의 특성(Fingerprint)이 자연스럽게 노출되어 봇 감지 시스템에 대한 내성이 강화됨을 확인하였다.

### 4. 인사이트 및 액션 (Insights & Action)

- **인사이트 (Insight):**
    - 화면이 존재하는 방식으로 데이터를 가져와봤다. 실제 봇을 감지 할 수 있는지 한번 확인해보자.
    - 단순히 엔진을 바꾸는 것을 넘어, 실행 환경(Display)을 제어하는 것이 크롤링의 성공률을 높이는 핵심적인 기술적 진보이다.
- **실행 방안 (Action Plan):**
    - 탐지 난이도가 높은 타겟 사이트에 대해 가상 화면 기반의 Headed 크롤링 엔진을 배포한다.
- **한 줄 결론 (Key Takeaway):**
    - 가상 화면과 Playwright의 조합은 서버 환경에서도 가장 현실적인 브라우저 자동화 환경을 제공한다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/webclient_pd.py){: target="_blank"}
- **다음 스텝 (Next Step):**
    - 구현된 클라이언트를 대상으로 다양한 봇 탐지 시나리오를 테스트할 수 있는 검증 서버를 구축한다.
