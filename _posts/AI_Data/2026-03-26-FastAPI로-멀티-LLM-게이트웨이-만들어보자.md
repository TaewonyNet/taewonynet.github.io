---
title: FastAPI로 멀티 LLM 게이트웨이 만들어보자
description: Gemini·Groq·Cerebras를 OpenAI 호환 /v1/chat/completions 하나로 묶고 Clean Architecture로 공급자를 교체 가능하게 만들었다
author: taewony
date: 2026-03-26 22:48:15 +0900
categories: [Quick, AI/Data]
tags: [fastapi, llm-gateway, openai-compatible, clean-architecture, routing, python]
pin: false
math: false
mermaid: false
---

## FastAPI로 멀티 LLM 게이트웨이 만들어보자
Gemini, Groq, Cerebras 키가 여러 개 있는데 API 형식이 다 달랐다. OpenAI SDK 그대로 쓰면서 뒤에서 공급자가 갈리는 게이트웨이를 만들었다.

### 1. 서론 (Introduction)
- **문제/상황 (Problem):** 여러 LLM 공급자를 쓰려면 각각 SDK를 따로 불러야 했다. 코드마다 공급자별 분기가 생겼고, 공급자를 바꾸면 호출부를 전부 고쳐야 했다.
- **목적 (Purpose):** OpenAI SDK 호환 엔드포인트 하나로 여러 공급자를 투명하게 라우팅한다.
- **대상 (Target Audience):** 여러 LLM 공급자를 코드 변경 없이 쓰고 싶은 개발자.

### 2. 방법 및 과정 (Methods & Process)
- **배경 조사 및 데이터 (Data Collection):** 공급자별로 인증 방식과 토큰 한도가 달라서 그대로 노출하면 클라이언트 코드가 공급자를 알아야 했다.

  | 공급자 | 토큰 한도(예) | 응답 포맷 |
  |---|---|---|
  | Gemini | 32768 | 자체 포맷 |
  | Groq | 8192 | OpenAI 호환 |
  | Cerebras | 8192 | OpenAI 호환 |

- **접근 방법 (Approach Methods):**
    - **[방법 1] OpenAI 호환 스키마 고정:** 요청/응답 스키마를 OpenAI `chat.completions` 형식으로 고정한다. 기존에 `openai.ChatCompletion.create`를 쓰던 코드는 `base_url`만 바꾸면 게이트웨이를 통과한다.
    - **[방법 2] 공통 인터페이스 뒤 어댑터 분리:** `ILLMProvider` 추상 클래스 하나를 두고 공급자마다 어댑터를 구현한다. 새 공급자가 늘어도 라우팅 로직과 API 레이어는 건드리지 않는다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** FastAPI, Pydantic, Python `abc.ABC`.
    - **주요 단계:** 요청 수신 $\rightarrow$ `model` 필드로 provider 매칭 $\rightarrow$ 해당 adapter 호출 $\rightarrow$ OpenAI 포맷으로 응답 변환.
    - **결과 도출 및 검증:** 데모 provider 3종(Gemini/Groq/Cerebras)을 등록하고 각각 모델명으로 요청했다. `gemini-2.5-flash`, `groq-llama3-70b`, `cerebras-llama3.1-8b` 요청 전부 200으로 라우팅됐고, 등록되지 않은 모델명은 400으로 명시적으로 거부됐다.

### 3. 결과 (Results)
- **분석 결과 요약:** 데모 provider 3개 등록 기준 요청 3건이 각각 올바른 adapter로 라우팅되어 200을 반환했다. 매칭되는 provider가 없는 모델명 요청은 400과 함께 어떤 모델이 문제인지 메시지로 반환됐다. 공급자 어댑터 하나 추가는 `ILLMProvider` 구현체 하나 작성으로 끝났고 라우터 코드는 수정하지 않았다.

### 4. 인사이트 및 액션 (Insights & Action)
- **인사이트 (Insight):** 호환 레이어 하나가 모든 공급자를 묶는다. 클라이언트 코드는 게이트웨이만 알면 되고, 공급자 교체가 비즈니스 로직에서 분리된 인프라 결정이 된다.
- **실행 방안 (Action Plan):** 공급자를 늘릴 때는 라우터를 고치는 대신 어댑터 하나만 추가하는 습관을 들인다. 도메인/서비스 레이어를 건드리지 않는 게 기준이다.
- **한 줄 결론 (Key Takeaway):** OpenAI 호환 게이트웨이 하나로 어떤 LLM 공급자든 교체 가능한 구조를 만들 수 있다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/llm_gateway_router.py){: target="_blank"}
- **다음 스텝 (Next Step):** 지금은 `model` 문자열 접두사로 provider를 매칭한다. 공급자·모델이 늘어나면 이 매칭 규칙이 하드코딩된 if-분기처럼 불어난다. 라우팅 규칙을 설정 파일이나 테이블로 외부화해서 코드 수정 없이 매핑을 바꿀 수 있게 하는 방향을 검토해야 한다.
