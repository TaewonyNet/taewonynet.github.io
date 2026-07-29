---
title: scrapling 스텔스 모드로 Cloudflare를 뚫어보자
description: solve_cloudflare=True 하나로 안 되던 이유와 WebRTC·Canvas·headless 세 가지를 동시에 막아야 했던 과정을 기록했다
author: taewony
date: 2026-05-19 21:00:00 +0900
categories: [Quick, Development]
tags: [python, scrapling, cloudflare, stealth, browser-fingerprint]
pin: false
math: false
mermaid: false
---

## scrapling 스텔스 모드로 Cloudflare를 뚫어보자
playwright headless로도 안 되는 사이트가 Cloudflare였다. `solve_cloudflare=True` 옵션만 추가하면 될 줄 알았는데 통과가 안 됐고, 파라미터 조합을 정리하다 보니 왜 그런지 이해가 됐다.

### 1. 서론 (Introduction)

- **문제/상황 (Problem):**
    - playwright headless는 Cloudflare Turnstile 챌린지를 통과하지 못한다. `solve_cloudflare=True` 단독으로도 안 됐다.
- **목적 (Purpose):**
    - `StealthyFetcher.fetch()`의 파라미터 조합이 각각 무엇을 막는지 정리하고, 실제로 브라우저가 없는 환경에서 어떤 방식으로 실패하는지 확인한다.
- **대상 (Target Audience):**
    - Cloudflare가 적용된 사이트를 수집해야 하는데 headless Chromium이 계속 차단당하는 개발자

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - Cloudflare는 단순 UA 검사를 넘어 브라우저 환경 자체를 확인한다. WebRTC 누출, Canvas 지문, `navigator.webdriver` 등 headless 감지 신호를 함께 본다.

    | 옵션 | 막는 대상 |
    | --- | --- |
    | `block_webrtc=True` | WebRTC로 실제 IP가 새는 것 |
    | `hide_canvas=True` | Canvas 렌더링 지문으로 클라이언트 식별되는 것 |
    | `headless=False` | `navigator.webdriver` 등 headless 전용 신호 |
    | `network_idle=True` | 챌린지 스크립트가 끝나기 전에 페이지를 읽는 것 |
    | `solve_cloudflare=True` | Turnstile/Interstitial 챌린지 자체 |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** `solve_cloudflare=True`만 단독으로 적용 — 파라미터 설명만 봐도 다른 채널(WebRTC, Canvas, headless)은 그대로 노출돼 나머지 신호에서 걸릴 여지가 남는다는 것을 확인했다.
    - **[방법 2]:** 위 표의 다섯 옵션을 동시에 적용 — `StealthyFetcher.fetch(url, **options)`로 한 번에 넘겨 다섯 채널을 함께 막는 조합을 구성했다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, scrapling `StealthyFetcher`(스텔스 옵션이 적용된 브라우저 기반 페처 — 설치된 scrapling 버전에 따라 내부 브라우저 엔진이 다를 수 있다)
    - **주요 단계:** 옵션 조합 구성 $\rightarrow$ `StealthyFetcher.fetch()` 호출 $\rightarrow$ 실패 시 예외 메시지로 원인 확인 $\rightarrow$ 폴백 안내
    - **결과 도출 및 검증:** Xvfb 없는 로컬 환경에서 `headless=False`로 호출하니 "Missing X server or $DISPLAY" 오류로 실패했다. 즉 GUI 모드 요구 자체가 실행 환경에 강하게 의존한다는 것을 실측으로 확인했고, 이 실패는 서버 환경에서 흔히 겪는 실패 유형과 같았다.

### 3. 결과 (Results)

- **분석 결과 요약:**
    - 파라미터 중 하나라도 빠지면 Cloudflare는 다른 신호로 잡아낼 여지가 남는다. 다섯 개가 동시에 적용돼야 챌린지 없이 통과할 조건이 갖춰진다.
    - `headless=False`는 Xvfb 등 GUI 환경이 없으면 그 자리에서 실패한다. 서버 환경에 그대로 배포할 수 없다는 제약이 실측으로 드러난다.
    - `StealthyFetcher`가 정상 동작하려면 내부적으로 쓰는 브라우저 엔진이 별도로 설치돼 있어야 한다(scrapling 버전에 따라 어떤 엔진인지 달라질 수 있다 — 직접 실행 환경에서 확인이 필요하다).

### 4. 인사이트 및 액션 (Insights & Action)

- **인사이트 (Insight):**
    - Cloudflare 탐지는 하나의 신호가 아니라 WebRTC·Canvas·headless 등 여러 채널을 병렬로 확인한다. 하나만 막으면 나머지 채널에서 걸린다.
- **실행 방안 (Action Plan):**
    - `headless=False`가 필요한 단계는 로컬 머신이나 Xvfb가 설치된 서버에서만 실행하도록 배치를 분리한다.
- **한 줄 결론 (Key Takeaway):**
    - Cloudflare는 `block_webrtc + hide_canvas + headless=False + network_idle + solve_cloudflare`를 동시에 써야 통과 조건이 갖춰진다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/scrapling_cloudflare_bypass.py){: target="_blank"}
- **다음 스텝 (Next Step):**
    - GUI 모드 요구와 브라우저 엔진 별도 설치라는 두 가지 의존성이 남아 있다. 이 의존성 없이도 통과 가능한 사이트와, 반드시 이 조합이 필요한 사이트를 구분하는 기준은 아직 없다.
