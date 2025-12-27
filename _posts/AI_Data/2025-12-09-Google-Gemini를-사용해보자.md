---
title: Google Gemini를 사용해 보자.
description: AI 중 가장 만만한 api인 Gemini를 사용해 보자.
author: taewony
date: 2025-12-09 22:35:30 +0900
categories: [Development, AI/Data]
tags: [Gemini api,google ai,free tier,ai development,prompt engineering]
pin: false
math: false
mermaid: false
---

## Google Gemini를 사용해 보자.
AI 중 가장 만만한 api인 Gemini를 사용해 보자.

### 1. 서론 (Introduction)
- **문제/상황 (Problem):**
    - AI를 API 형태로 이용하고 싶다. 
- **목적 (Purpose):**
    - 돈 없이 AI를 활용한 다양한 작업을 하기 위해서 기본 도구를 만든다.
- **대상 (Target Audience):**
    - 돈 없는 나를 위해 

### 2. 방법 및 과정 (Methods & Process)
- **배경 조사 및 데이터 (Data Collection):**
  - 생성형 ai의 api 제공과 무료 티어 조사 후 Gemini를 사용하보기로 한다.
	- 무료 생성형 AI API 비교표 (2025 기준, 무료 한도 저렴 순)
  
| 모델/API                  | 무료 사용 한도                                   | 장점                                                   | 단점                                                   | 주요 사용처                          |
|---------------------------|--------------------------------------------------|--------------------------------------------------------|--------------------------------------------------------|--------------------------------------|
| **Google Gemini API**     | Google AI Studio에서 무료 시작, 입력/출력 토큰 무료 | 최신 멀티모달 모델, 이미지·텍스트 모두 지원             | 고급 기능은 유료, 일부 모델 제한                       | 대화형 앱, 멀티모달 연구, 프로토타입 |
| **Microsoft Copilot API** | Windows/Edge/앱 내 무료 사용, 일부 기능 무제한   | 텍스트·이미지·음성·검색 통합, 생산성 도구와 연동        | 독립 API보다는 플랫폼 내 사용 중심                     | 오피스 자동화, 검색, 대화형 에이전트 |
| **Hugging Face API**      | 오픈소스 모델 무료 호출 (제한적)                 | 다양한 모델 선택, 커스터마이징 가능                     | 속도/성능은 상용 API보다 낮을 수 있음                  | 연구, 프로토타입, 맞춤형 모델 배포   |
| **Clarifai API**          | 월 1,000회 무료 호출                             | 다양한 비전 모델, 커스텀 학습 지원                     | 무료 호출 수 제한                                      | 이미지 분류, 얼굴 인식, 비전 AI      |
| **DeepL API**             | 월 500,000자 무료 번역                           | 자연스러운 번역 품질, 다국어 지원                      | 번역 전용, 무료 한도 초과 시 유료                      | 문서 번역, 앱 내 번역 기능           |
| **Cloudmersive API**      | 월 수천 회 무료 호출                             | 다양한 모듈(텍스트, 이미지, 데이터 처리) 제공          | 고급 기능은 유료, 속도 제한                            | OCR, 데이터 처리, 간단한 AI 기능     |
| **OpenAI API (GPT-4/5)**  | 신규 가입 시 무료 크레딧 제공 (일정 토큰 한도)   | 강력한 자연어 처리, 다양한 기능(요약, 번역, 분석 등)   | 무료 크레딧 소진 후 유료, 토큰 단가 높음               | 챗봇, 문서 요약, 코드 생성, 고객지원 |
| **Claude API (Anthropic)**| 무료 체험 토큰 제공                              | 장문 처리에 강점, 안전성 높은 설계                     | 한국어 지원 상대적으로 제한적                          | 리서치, 보고서 작성, 대화형 에이전트 |
| **Stability AI (Stable Diffusion)** | 월별 무료 크레딧 제공                  | 고품질 이미지 생성, 오픈소스 기반                      | GPU 자원 소모 큼, 무료 크레딧 제한                     | 이미지 합성, 디자인, 예술 창작       |
| **Google Cloud Vision API** | 신규 가입 시 $300 크레딧 제공                  | 객체 인식, OCR, 이미지 분석 강력                       | 무료 크레딧 이후 유료, 생성형보다는 인식 특화          | 이미지 분석, 문서 스캔, 데이터 처리  |
| **AssemblyAI**            | 일정 시간 무료 음성 처리 제공                    | 음성 인식(STT), 실시간 처리 지원                       | 무료 시간 제한, 고급 기능은 유료                       | 음성→텍스트 변환, 팟캐스트 분석      |
| **Azure Cognitive Services** | 일부 서비스 무료 티어 제공                     | 음성, 텍스트, 이미지 등 종합 AI 기능                   | 무료 티어 제한, 사용량 증가 시 비용 발생               | 기업용 챗봇, 음성 서비스, 번역        |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** Google 및 Perplexity를 활용하여 주요 AI API를 조사한다.
    - **[방법 2]:** 조사한 내용을 바탕으로 가장 적합한 API 확인 후 활용방법을 확인한다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** Python 
    - **주요 단계:** 
		1. 무료 AI API 비교 조사한다.
		2. Google Gemini API의 비용 확인 및 활용 결정한다.
		3. 코드를 작성한다.
    - **결과 도출 및 검증:** 저렴한 기준으로 Gemini API가 제일 우선순위에 있음을 확인하였으며 실제로 할용하기로 한다.

### 3. 결과 (Results)
- **분석 결과 요약:**
    - Google AI Studio에서 키를 발급 받아 사용이 가능하며 현 시점 무료 티어가 가장 많고 사용할 수 있는 모델에 따라 여러가지 활용 방안이 있음을 확인되었다.

### 4. 인사이트 및 액션 (Insights & Action)
- **인사이트 (Insight):**
    - 현 시점기준으로 Google Gemini API가 다른 AI에 비해 무료 시작도 가능하며 및 저렴한 비용으로 부담없이 사용 가능하다.
- **실행 방안 (Action Plan):**
    - [Google AI Studio](https://aistudio.google.com/api-keys){: target="_blank"}에서 키를 발급받고 프롬프트 샘플을 작성한다. 
- **한 줄 결론 (Key Takeaway):**
    - Gemini API를 활용하여 개인 AI 프로젝트에 사용한다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/gemini.py){: target="_blank"}
- **다음 스텝 (Next Step):**
    - 프롬프트 엔지니어링을 적용한 간단한 프로젝트를 만들어보자.
