---
title: GitHub를 저장소로, Colab을 무료 컴퓨트로 쓰는 크롤 자동화
description: PyGithub로 크롤 결과를 커밋으로 남기고, Colab 세션이 꺼져도 이어서 실행하는 방법을 정리했다
author: taewony
date: 2026-03-24 21:00:00 +0900
categories: [Quick, Development]
tags: [python, google-colab, github, pygithub, web-crawling, automation]
pin: false
math: false
mermaid: false
---

## GitHub를 저장소로, Colab을 무료 컴퓨트로 쓰는 크롤 자동화
Colab 크롤러의 가장 큰 약점은 세션이 끊기면 수집 결과가 통째로 사라진다는 점이다. GitHub 리포지토리를 상태 저장소처럼 쓰면 코드·설정·결과가 한 곳에 남는다.

### 1. 서론 (Introduction)
- **문제/상황 (Problem):** Colab 무료 세션은 최대 12시간, 연결이 끊기면 `/content` 전체가 초기화된다. 크롤 결과를 로컬에 쌓아두면 세션 종료 후 복구 방법이 없다.
- **목적 (Purpose):** PyGithub로 GitHub 리포지토리에 결과 파일을 커밋하면, 세션이 꺼져도 이어 실행 가능한 상태가 된다.
- **대상 (Target Audience):** Colab 무료 컴퓨트 + GitHub 조합으로 소규모 크롤 파이프라인을 구성하려는 파이썬 개발자

### 2. 방법 및 과정 (Methods & Process)
- **배경 조사 및 데이터 (Data Collection):**
    - Colab 셀에서 PAT(Personal Access Token)을 포함한 git clone URL로 private 리포지토리를 가져온다. `os.chdir()`로 이동 후 메인 스크립트를 `exec()`으로 실행하면 Colab 런타임 변수와 같은 스코프에서 동작한다.
    - GitHub Contents API로 파일을 업데이트할 때는 현재 파일의 SHA가 반드시 필요하다. `update_file()` 호출 전에 `get_contents()`로 SHA를 먼저 가져오는 것이 핵심이다.
    - Dependabot·CI와 무관하게, GitHub 리포지토리 자체가 코드·설정·크롤 결과를 한곳에 담는 파일 단위 DB 역할을 한다.
- **접근 방법 (Approach Methods):**
    - **[방법 1]:** `read_file(path)`로 이전 실행 결과를 `bytes`로 읽어와 중복 제거·병합 판단에 쓴다.
    - **[방법 2]:** `save_file(path, content)` — 파일이 있으면 `get_contents()`로 SHA를 조회해 `update_file()`, 없으면 `create_file()`. 커밋 메시지에 실행 시각을 자동 삽입해 추적 가능하게 한다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Google Colab, PyGithub, GitHub Contents API
    - **주요 단계:** `git clone`으로 리포지토리·설정 확보 $\rightarrow$ 크롤러 실행 $\rightarrow$ 결과를 `bytes`로 직렬화 $\rightarrow$ `save_file()`로 SHA 확인 후 커밋 $\rightarrow$ 세션 재시작 시 같은 `git clone`으로 직전 상태 복원
    - **결과 도출 및 검증:** 첫 실행은 파일이 없어 `create_file()` 경로를 타고, 같은 경로에 두 번째 저장을 시도하면 직전 SHA를 조회해 `update_file()` 경로를 탄다. SHA가 어긋나면 409(SHA 불일치)로 실패해 동시 쓰기 충돌을 드러낸다.

### 3. 결과 (Results)
- **분석 결과 요약:** 크롤 결과 파일이 GitHub 커밋 히스토리로 남아 실행 시각·변경 내용을 추적할 수 있다. 세션 초기화 후에도 리포지토리에서 직전 상태를 내려받아 중단 지점부터 재실행 가능하다. PAT 권한을 `contents:write`로 최소화하면 토큰 유출 시 피해 범위를 줄일 수 있다.

### 4. 인사이트 및 액션 (Insights & Action)
- **인사이트 (Insight):** GitHub 리포지토리는 파일 단위 DB처럼 동작한다. `save_file()`의 SHA 패턴만 익히면 `git` CLI 없이 커밋까지 자동화된다.
- **실행 방안 (Action Plan):** `read_file()`로 이전 수집 목록을 불러와 중복 제거 후 `save_file()`로 병합하면 멱등(idempotent) 크롤러가 된다.
- **한 줄 결론 (Key Takeaway):** Colab이 꺼져도 GitHub에 커밋이 남아 있으면 크롤러는 죽지 않는다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/colab_github_store.py){: target="_blank"}
- **다음 스텝 (Next Step):** 같은 파일을 두 세션이 동시에 업데이트하면 SHA 충돌로 409 에러가 반환된다. 파일을 날짜·배치 단위로 분리하면 충돌 없이 병렬 실행할 수 있다.
