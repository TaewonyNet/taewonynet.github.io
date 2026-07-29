---
title: 로컬 LLM(Ollama·CLI)을 OpenAI 호환 엔드포인트로 감싸보자
description: Ollama와 CLI 기반 로컬 LLM을 게이트웨이 뒤에 붙여 인터넷 없이도 같은 API로 추론하는 구조를 만들었다
author: taewony
date: 2026-04-10 22:09:31 +0900
categories: [Quick, AI/Data]
tags: [ollama, local llm, subprocess, openai-sdk, self-hosting, llm-gateway]
pin: false
math: false
mermaid: false
---

## 로컬 LLM(Ollama·CLI)을 OpenAI 호환 엔드포인트로 감싸보자
Ollama가 로컬에서 잘 돌아가는데 게이트웨이와는 별도로 호출해야 했다. subprocess로 감싸서 같은 응답 포맷으로 맞췄다.

### 1. 서론 (Introduction)
- **문제/상황 (Problem):** 로컬 LLM은 CLI나 자체 API로만 호출 가능해서 게이트웨이와 별도 코드 경로가 필요했다. 비용이 들지 않는 로컬 LLM을 클라우드 앞에 두고 싶었다.
- **목적 (Purpose):** 로컬 커맨드 실행 결과를 OpenAI 호환 응답 딕셔너리로 감싸 같은 `/v1/chat/completions` 형식으로 접근한다.
- **대상 (Target Audience):** 로컬 LLM을 기존 LLM 파이프라인에 통합하고 싶은 개발자.

### 2. 방법 및 과정 (Methods & Process)
- **배경 조사 및 데이터 (Data Collection):** 로컬 LLM 연동 방식은 크게 두 갈래다.

  | 방식 | 호출 경로 | 비용 |
  |---|---|---|
  | Ollama HTTP API | `localhost:11434/api/chat` | 무료(로컬 자원만 소모) |
  | CLI 전용 로컬 LLM | `subprocess.run()`으로 실행 | 무료(로컬 자원만 소모) |

- **접근 방법 (Approach Methods):**
    - **[방법 1] subprocess로 로컬 커맨드 실행:** `subprocess.run()`에 커맨드 리스트를 넘기고 `capture_output=True`로 stdout을 받는다. 타임아웃을 명시해 hang을 방지한다.
    - **[방법 2] OpenAI 응답 포맷으로 변환:** stdout 텍스트를 `choices[0].message.content`에 넣고 `id`·`model`·`usage` 필드를 채워 게이트웨이의 다른 응답과 동일한 형태로 맞춘다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python `subprocess.run`, `time.perf_counter()`.
    - **주요 단계:** 커맨드 구성 $\rightarrow$ `subprocess.run()` 실행·stdout 캡처 $\rightarrow$ 실패 시 returncode/stderr로 예외 발생 $\rightarrow$ 성공 시 OpenAI 포맷 딕셔너리로 래핑.
    - **결과 도출 및 검증:** echo 스텁 커맨드로 데모를 실행하자 0.0013초 만에 응답이 반환되고 OpenAI 호환 딕셔너리(`choices`, `usage` 포함)로 감싸졌다. 존재하지 않는 바이너리를 지정하면 `FileNotFoundError`가 그대로 올라와 실패가 명확히 드러났다.

### 3. 결과 (Results)
- **분석 결과 요약:** 로컬 커맨드 실행 결과가 클라우드 provider 응답과 동일한 스키마로 반환됐다. 클라이언트 입장에서는 로컬인지 클라우드인지 구분할 필요가 없었다. 실패한 로컬 커맨드는 예외로 곧바로 드러나 실패를 숨기지 않았다.

### 4. 인사이트 및 액션 (Insights & Action)
- **인사이트 (Insight):** 로컬 LLM을 게이트웨이에 붙이면 비용 제어가 코드 수준이 아니라 인프라 수준으로 올라간다. 클라이언트는 그냥 요청만 하면 된다.
- **실행 방안 (Action Plan):** 실제 환경에서는 echo 스텁 대신 `ollama run <model> <prompt>` 같은 실커맨드로 교체하고, 타임아웃과 stderr 로깅을 반드시 남긴다.
- **한 줄 결론 (Key Takeaway):** subprocess 어댑터 하나로 로컬 LLM을 게이트웨이의 provider 중 하나로 편입시킬 수 있다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/llm_local_openai_compat.py){: target="_blank"}
- **다음 스텝 (Next Step):** 지금은 프로세스 하나를 실행하고 끝날 때까지 기다리는 동기 방식이다. 응답이 길어지는 로컬 모델에서는 stdout을 라인 단위로 스트리밍해 토큰이 생성되는 대로 넘기는 방식이 필요하다.
