---
title: LLMLingua-2로 긴 LLM 컨텍스트 압축하기
description: LLMLingua-2 같은 압축 모델이 없는 환경에서도 문장 중요도 기반 추출요약으로 목표 토큰 수를 맞추는 폴백을 만들었다
author: taewony
date: 2026-04-24 22:28:54 +0900
categories: [Quick, AI/Data]
tags: [llmlingua, prompt-compression, context-window, tokens, python]
pin: false
math: false
mermaid: false
---

## LLMLingua-2로 긴 LLM 컨텍스트 압축하기
RAG로 가져온 문서가 길어서 토큰 한도를 초과하고 비용도 늘었다. 압축 모델을 못 쓰는 환경에서도 쓸 수 있는 폴백이 필요했다.

### 1. 서론 (Introduction)
- **문제/상황 (Problem):** 긴 문서를 LLM에 넣으면 토큰 한도 초과 오류가 나거나 비용이 크게 늘었다. 단순 트런케이션은 중간에 있는 핵심 정보를 잘라냈다. LLMLingua-2 같은 압축 모델을 오프라인이나 모델 다운로드 실패 환경에서는 못 쓸 수도 있다.
- **목적 (Purpose):** 압축 모델 없이도 목표 토큰 수에 맞춰 문서를 줄이는 추출요약 폴백을 만든다.
- **대상 (Target Audience):** LLM 토큰 비용과 컨텍스트 한도 문제를 해결하고 싶은 개발자.

### 2. 방법 및 과정 (Methods & Process)
- **배경 조사 및 데이터 (Data Collection):** Microsoft가 공개한 LLMLingua-2 계열 모델은 문장 중 LLM 추론에 중요한 토큰을 식별해 나머지를 제거하는 방식이다. 다만 모델 다운로드가 안 되거나 오프라인인 환경에서는 이 방식 자체를 못 쓴다 — 그럴 때 쓸 대체 로직이 필요했다.
- **접근 방법 (Approach Methods):**
    - **[방법 1]:** 문장 단위로 쪼갠다. 마침표·물음표·느낌표 등으로 문장을 분리하고 각 문장의 토큰 수(공백 기준 단어 수로 근사)를 센다.
    - **[방법 2]:** 문장 길이·키워드 빈도 휴리스틱으로 중요도를 매겨, 점수 높은 문장부터 목표 토큰 수에 맞을 때까지 원문 순서를 지켜 채우는 추출요약을 만든다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** 표준 라이브러리 기반 문장 분리·빈도 계산(외부 모델 의존 없음).
    - **주요 단계:** 문서 입력 $\rightarrow$ 문장 분리 $\rightarrow$ 문장별 중요도 점수 계산 $\rightarrow$ 점수 높은 순으로 목표 토큰 예산까지 채우기 $\rightarrow$ 원문 순서로 재정렬.
    - **결과 도출 및 검증:** 65토큰짜리 예시 문서를 목표 30토큰/15토큰으로 각각 압축해보니, 목표 토큰 수 근처로 줄어들면서도 점수가 높은 문장 위주로 남는 것을 확인했다.

### 3. 결과 (Results)
- **분석 결과 요약:** 압축 모델 없이도 문장 중요도 기반 추출요약만으로 목표 토큰 예산에 맞춰 문서를 줄일 수 있었다. 실제 LLMLingua-2 모델을 붙였을 때의 압축률·응답 품질은 아직 실측하지 않았다 — 이 PoC는 폴백 로직만 구현한 상태다.

### 4. 인사이트 및 액션 (Insights & Action)
- **인사이트 (Insight):** 압축 모델이 없어도 "문장 단위로 쪼개 중요도 순으로 채운다"는 단순한 규칙만으로 목표 토큰 예산을 지킬 수 있는 폴백을 만들 수 있다.
- **실행 방안 (Action Plan):** 압축 모델이 있는 환경에서는 LLMLingua-2를 우선 쓰고, 이 폴백은 모델이 없거나 실패했을 때만 쓰는 이중 구조로 붙인다.
- **한 줄 결론 (Key Takeaway):** 압축 모델이 없어도 문장 중요도 기반 추출요약으로 목표 토큰 수를 맞출 수 있다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/llm_context_compress.py){: target="_blank"}
- **다음 스텝 (Next Step):** 실제 LLMLingua-2 모델을 붙여 이 폴백과 압축률·응답 품질을 비교하는 실험이 필요하다. 키워드 빈도 계산도 TF-IDF 등으로 고도화할 여지가 있다.
