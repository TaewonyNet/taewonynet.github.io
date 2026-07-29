---
title: scrapling으로 사이트 수집을 해보자
description: requests와 playwright로 안 되는 사이트를 StealthyFetcher 한 줄로 통과한 과정을 기록했다
author: taewony
date: 2026-05-15 21:00:00 +0900
categories: [Quick, Development]
tags: [python, scrapling, web-scraping, stealthy-fetcher]
pin: false
math: false
mermaid: false
---

## scrapling으로 사이트 수집을 해보자
playwright headless로 크롤러를 만들었는데 여전히 막히는 사이트가 있었다. scrapling 한 줄로 같은 대상을 통과한 과정과, 응답을 실제 콘텐츠로 신뢰할 수 있는지 코드로 판단하는 방법을 정리했다.

### 1. 서론 (Introduction)

- **문제/상황 (Problem):**
    - playwright headless로 수집해도 일부 사이트는 챌린지 페이지만 반환한다. 응답 코드는 200이라 오류로 잡히지 않는다.
- **목적 (Purpose):**
    - scrapling의 Fetcher/StealthyFetcher로 챌린지 없이 실제 HTML을 수집하고, 응답이 진짜 콘텐츠인지 코드에서 판단할 수 있는 구조를 만든다.
- **대상 (Target Audience):**
    - requests나 playwright로 차단당한 사이트를 수집해야 하는 파이썬 개발자

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - scrapling은 `Fetcher`(단순 HTTP)와 `StealthyFetcher`(브라우저 기반 스텔스) 두 계층으로 나뉜다. 가벼운 수집엔 `Fetcher.get(url)`, 차단이 있는 사이트엔 `StealthyFetcher`를 쓰는 식으로 대상에 맞춰 고른다.

    | 구성 요소 | 역할 |
    | --- | --- |
    | `Fetcher.get(url)` | HTTP 요청, 반환값에 `.css()`·`.get_all_text()` 제공 |
    | `StealthyFetcher.fetch(url, ...)` | 브라우저 기반 수집, 봇 우회 옵션 다수 |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** `Fetcher.get(url)`로 요청 후 `page.css(selector)`로 원하는 노드만 뽑는다.
    - **[방법 2]:** 셀렉터를 안 주면 `get_all_text()`로 페이지 전체 텍스트를 받는다. 셀렉터 지정 여부에 따라 같은 요청 결과를 다르게 추출하는 셈이다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, scrapling(`Fetcher`), `http.server`(로컬 검증용)
    - **주요 단계:** 로컬 데모 서버 기동 $\rightarrow$ `Fetcher.get()` 요청 $\rightarrow$ `.css()`로 셀렉터 추출 $\rightarrow$ `.get_all_text()`로 전체 텍스트 추출
    - **결과 도출 및 검증:** 로컬 서버(`<h1 class="title">`)에 대해 `Fetcher.get()`이 status 200을 받았고, `.css(".title")`로 "데모 페이지" 텍스트를, `.get_all_text()`로 본문 전체를 그대로 뽑아냈다. 코드 변경은 요청·파싱 각각 한 줄이었다.

### 3. 결과 (Results)

- **분석 결과 요약:**
    - `Fetcher.get(url).css(selector)` 한 줄로 셀렉터 기반 추출이 끝났다.
    - 응답 코드가 200이어도 실제 콘텐츠인지는 별도로 확인해야 한다는 것을 실무에서 반복 확인했다(ux.py의 `_is_blocked()`가 이 역할).
    - 셀렉터를 주면 노드 텍스트만, 안 주면 전체 텍스트를 반환하도록 함수 하나로 두 모드를 다 처리했다.

### 4. 인사이트 및 액션 (Insights & Action)

- **인사이트 (Insight):**
    - 수집 성공 여부를 HTTP 상태 코드만으로 판단하면 잘못된 데이터를 모르고 쌓는다. 응답 HTML 안의 신호까지 확인하는 한 단계가 필요하다.
- **실행 방안 (Action Plan):**
    - 차단 판정 로직은 `Fetcher.get()` 결과에 공통으로 적용하는 유틸로 빼둔다.
- **한 줄 결론 (Key Takeaway):**
    - scrapling은 설치 한 줄, 호출 한 줄로 requests보다 한 단계 편한 파싱 인터페이스를 제공한다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/scrapling_basic_fetch.py){: target="_blank"}
- **다음 스텝 (Next Step):**
    - 기본 `Fetcher`는 응답을 그대로 돌려줄 뿐 차단 여부를 스스로 판단하지 않는다. 봇 차단 신호를 감지하는 로직은 호출부에서 별도로 얹어야 한다는 한계가 남는다.
