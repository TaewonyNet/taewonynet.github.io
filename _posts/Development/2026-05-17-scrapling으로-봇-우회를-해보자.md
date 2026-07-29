---
title: scrapling으로 봇 우회를 해보자
description: curl_cffi부터 playwright까지 빠른 방법 순으로 시도하고 도메인별 성공 방법을 캐싱하는 구조를 만들었다
author: taewony
date: 2026-05-17 21:00:00 +0900
categories: [Quick, Development]
tags: [python, scrapling, curl-cffi, playwright, bot-bypass, method-cache]
pin: false
math: false
mermaid: false
---

## scrapling으로 봇 우회를 해보자
StealthyFetcher 하나만 써도 되긴 하는데, 모든 사이트에 최고 단계 수집기를 붙이면 속도가 나지 않는다. 헤더·UA 조합을 바꿔가며 어디까지 가벼운 방법으로 통과하는지 확인하는 구조를 만들었다.

### 1. 서론 (Introduction)

- **문제/상황 (Problem):**
    - 브라우저 기반 수집기(StealthyFetcher 등)는 느리다. 차단이 없는 사이트에 쓰면 낭비다. 도메인마다 최소 비용의 수집 방법이 다르다.
- **목적 (Purpose):**
    - 헤더/UA 조합을 가벼운 것부터 순서대로 시도하고, 403 등 차단 신호가 나오면 다음 조합으로 넘어가는 최소 폴백 구조를 만든다.
- **대상 (Target Audience):**
    - 여러 도메인을 반복 수집하면서 속도와 통과율을 함께 잡고 싶은 파이썬 개발자

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - 실무 수집기(ux.py)에서는 curl_cffi → playwright → StealthyFetcher → 실제 Chrome 프로필 순으로 4단계 폴백을 쓴다. 그중 가장 앞단인 "헤더/UA만으로 얼마나 통과되는가"를 이 글에서 따로 떼어 확인한다.

    | 헤더 조합 | 내용 | 통과 대상 |
    | --- | --- | --- |
    | 최소 | `User-Agent: python-requests` | 헤더 검사 없는 사이트 |
    | 브라우저 UA | Chrome UA만 추가 | 단순 UA 차단 |
    | 브라우저 UA + Referer/Accept-Language | 전체 헤더 세트 | UA+헤더 조합 검사 |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** 헤더 조합 리스트를 순서대로 시도하며 상태 코드(401/403/429)와 응답 본문의 차단 서명("access denied", "captcha" 등)을 함께 확인한다.
    - **[방법 2]:** 통과하지 못하면 다음 조합으로 넘어가고, 모든 조합이 실패하면 마지막 결과를 그대로 반환해 호출자가 차단 여부를 판단하게 한다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, `urllib.request`(표준 라이브러리), `http.server`(로컬 검증용)
    - **주요 단계:** 헤더 조합 목록 순회 $\rightarrow$ 요청 $\rightarrow$ 상태 코드·본문 서명 확인 $\rightarrow$ 통과 시 즉시 반환, 아니면 다음 조합
    - **결과 도출 및 검증:** UA 검사만 하는 로컬 게이트(비 Chrome UA는 403)에 대해 최소 헤더(`python-requests`)는 403으로 차단됐고, 브라우저 UA로 바꾼 두 번째 조합에서 status 200으로 통과했다.

### 3. 결과 (Results)

- **분석 결과 요약:**
    - 단순 UA 검사 수준의 차단은 헤더 조합만 바꿔도 통과한다.
    - HTTP 200을 받았어도 차단일 수 있어 본문 서명 확인 단계가 별도로 필요하다.
    - 헤더만으로 못 뚫는 사이트는 더 무거운 단계(playwright, StealthyFetcher)로 넘겨야 한다.

### 4. 인사이트 및 액션 (Insights & Action)

- **인사이트 (Insight):**
    - 수집 방법의 단계가 올라갈수록 속도가 느려진다. 가벼운 헤더 조합으로 통과되는 사이트에 굳이 브라우저를 띄울 필요가 없다.
- **실행 방안 (Action Plan):**
    - 헤더 조합 폴백을 가장 앞단에 두고, 여기서 통과 못한 도메인만 playwright·StealthyFetcher로 승격한다.
- **한 줄 결론 (Key Takeaway):**
    - 빠른 헤더 조합부터 시도하고 차단 신호가 보일 때만 다음 조합으로 넘어가는 순서가 속도와 통과율을 동시에 잡는다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/scrapling_stealth_fetch.py){: target="_blank"}
- **다음 스텝 (Next Step):**
    - 헤더 조합은 단순 UA·헤더 검사만 우회한다. 브라우저 환경 자체(자바스크립트 실행, 지문 검사)를 확인하는 차단에는 한계가 있고, 이 경우 정적 요청 방식 자체로는 통과가 안 된다는 한계가 남는다.
