---
title: VPN 확장 자동화 — Chrome 차단을 Playwright로 해결했다
description: --load-extension이 Chrome 업데이트로 막힌 뒤 Playwright Chromium으로 우회해 IP를 확인해보자
author: taewony
date: 2026-02-28 23:11:07 +0900
categories: [Quick, Development]
tags: [python, playwright, chrome-extension, vpn, automation]
pin: false
math: false
mermaid: false
---

## VPN 확장 자동화 — Chrome 차단을 Playwright로 해결했다
앞 글의 셀레니움 방식이 Chrome 업데이트 후 갑자기 막혔다. `--load-extension`이 바이너리 수준에서 차단된 원인을 파고들어 Playwright Chromium으로 대체해 우회를 복구했다.

### 1. 서론 (Introduction)

- **문제/상황 (Problem):**
    - 앞 글에서 완성한 `selenium_vpn_ip.py`가 Chrome 업데이트 이후 확장을 로드하지 못하고 바로 실패한다.
    - `chrome://extensions`의 shadow DOM에서 VPN 확장 ID 조회 결과가 빈 배열 `[]`로 돌아온다.
- **목적 (Purpose):**
    - 차단 원인을 확인하고 현재 환경에서도 확장을 로드해 국가 선택·IP 검증을 복구한다.
- **대상 (Target Audience):**
    - 셀레니움 + 크롬 확장 자동화 중 Chrome 업데이트 후 갑자기 막힌 개발자

### 2. 방법 및 과정 (Methods & Process)

- **배경 조사 및 데이터 (Data Collection):**
    - Chrome 바이너리에 `--enable-logging=stderr --vmodule=extension_service*=5`를 붙여 실행하니 즉시 원인이 드러났다. 로그에 `extension_service.cc:420  browser_defaults::kAllowExtensionsLoading = false`와 `--load-extension is not allowed in Google Chrome, ignoring.`가 찍혔다.

    Google Chrome 130부터 `kAllowExtensionsLoading`이 `false`로 컴파일됐다. 플래그·CDP·Preferences 파일 조작 모두 이 컴파일 값 앞에서 무효다.

| 시도한 우회 방법 | 결과 |
| --- | --- |
| `--load-extension` 직접 전달 | `ignoring.` — 차단 |
| `add_extension()` CRX | 동일 차단 |
| CDP `Extensions.loadUnpacked` | `Method not available` |
| Preferences 파일 수동 수정 | Secure MAC 검증 거부 |
| 영구 프로필 + 웹 스토어 수동 설치 | 1회 수동 작업 필요, 이후 동작 |

    Playwright가 번들로 가져오는 Chromium은 Google Chrome이 아니라 이 컴파일 제한이 없다.

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** 영구 프로필 — 웹 스토어에서 확장을 수동 설치한 뒤 `--user-data-dir`로 프로필을 재사용. 최초 1회 수동 작업이 필요하지만 Google Chrome에서도 동작한다.
    - **[방법 2]:** Playwright Chromium — `download()`로 CRX를 받아 압축 해제한 뒤 Playwright Chromium에 `--load-extension`으로 로드. 완전 자동, Google Chrome 버전 제약 없음.

- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python, playwright, pyvirtualdisplay, chrome_ext_downloader
    - **주요 단계:**
        1. `download()` → CRX 다운로드 + 압축 해제 + `update_url` 제거
        2. Playwright Chromium + `ignore_default_args=["--disable-extensions"]` + `--load-extension=<압축해제경로>`
        3. `chrome://extensions-internals` JSON에서 런타임 ID 읽기 (shadow DOM 불필요)
        4. 팝업 열기 → 스플래시 숨김 대기 → 온보딩 4단계 → 지역 목록 → 검색 → 국가·지역 클릭 → 연결 → IP 비교
    - **온보딩 4단계 (v4.x):** `.free-step__btn` → `.premium-step__btn` → `.pricing-step__action--free` → `.trial-modal__close`
    - **결과 도출 및 검증:** `api.ip.pe.kr` IP가 한국 주소에서 영국 주소로 바뀌었다.

### 3. 결과 (Results)

- **분석 결과 요약:**
    - 우회 성공. `--load-extension`이 막힌 환경에서 Playwright Chromium으로 복구했다.
    - Playwright `ignore_default_args=["--disable-extensions"]`를 빠뜨리면 Playwright가 자동으로 `--disable-extensions`를 추가해 확장이 로드되지 않는다.
    - Playwright 번들 Chromium은 버전마다 SIGTRAP 등 안정성 차이가 있다. 최신 버전 디렉터리를 자동으로 선택하는 로직이 필요하다.

### 4. 인사이트 및 액션 (Insights & Action)

- **인사이트 (Insight):**
    - Google Chrome과 Chromium은 같은 코드 베이스지만 배포 시 컴파일 플래그가 다르다. `--load-extension` 차단은 Google이 배포하는 Chrome 바이너리에만 적용된다.
    - Playwright는 자동화 목적의 Chromium을 번들로 가져온다. 이 Chromium이 Selenium이 쓰는 Google Chrome보다 자동화 친화적이다.
    - `ignore_default_args`는 Playwright가 조용히 추가하는 플래그를 명시적으로 제거하는 탈출구다. 확장 자동화할 때는 `--disable-extensions` 제거가 필수다.
- **실행 방안 (Action Plan):**
    - 확장이 업데이트되면 온보딩 흐름과 선택자가 또 바뀐다. 선택자 실패를 조용히 삼키지 않고 즉시 에러로 드러내는 관리 레이어를 다음에 붙여보자.
- **한 줄 결론 (Key Takeaway):**
    - Google Chrome의 `--load-extension` 차단은 Playwright Chromium + `ignore_default_args=["--disable-extensions"]`로 우회할 수 있다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/playwright_vpn_ip.py){: target="_blank"}
- **다음 스텝 (Next Step):**
    - 확장 UI가 바뀌면 자동화가 조용히 실패한다. 다음엔 확장을 안전하게 관리해 화면이 바뀌면 에러로 드러나게 해보자.
