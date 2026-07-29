---
title: PyTorch 없이 CPU에서 cross-encoder 리랭킹을 해보자
description: onnxruntime 기반 cross-encoder와 스레드 튜닝으로 CPU 리랭킹 지연을 2463ms에서 565ms로 줄였다. 그전엔 잘못된 측정 조건 때문에 리랭킹 자체를 뺐었다
author: taewony
date: 2026-07-15 23:29:53 +0900
categories: [Quick, AI/Data]
tags: [reranking, cross-encoder, onnxruntime, cpu-inference, search, benchmark]
pin: false
math: false
mermaid: false
---

## PyTorch 없이 CPU에서 cross-encoder 리랭킹을 해보자
개인 검색 인프라 프로젝트에서 1차 검색 결과를 질문과의 관련성으로 재정렬하고 싶었는데, PyTorch 기반 cross-encoder는 CPU에서 너무 느렸다. 그런데 "너무 느리다"는 판단 자체가 한동안 잘못된 측정 조건에서 나온 결론이었다.

### 1. 서론 (Introduction)
- **문제/상황 (Problem):** 검색 1차 결과를 리랭킹하고 싶은데, 일반적인 cross-encoder는 PyTorch가 필요해 무겁고 CPU에서 느리다.
- **목적 (Purpose):** PyTorch 없이 onnxruntime 기반 cross-encoder로 CPU 리랭킹 지연을 실사용 가능한 수준까지 줄인다.
- **대상 (Target Audience):** GPU 없이 CPU 서버에서 검색 리랭킹을 붙이려는 개발자.

### 2. 방법 및 과정 (Methods & Process)
- **배경 조사 및 데이터 (Data Collection):** 같은 리랭킹 로직을 조건별로 측정한 지연 시간을 정리했다.

  | 조건 | 지연 | 비고 |
  |---|---|---|
  | PyTorch fp32, 콜드로드+512토큰 | 12.5초 | 이 값 때문에 한때 리랭킹을 파이프라인에서 제외 |
  | PyTorch fp32(정상 측정) | 2463ms | 정확도 74.2% |
  | onnxruntime(fastembed), 기본 스레드 | 565ms | 정확도 74.2%로 동일, 4.4배 빠름 |
  | onnxruntime, threads=8 | 949ms(1187ms에서) | 스레드 튜닝만으로 약 20% 추가 개선 |
  | production 평균 | 1034ms(2137ms에서) | 최종 반영 후 실측 |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** PyTorch fp32 cross-encoder를 그대로 쓴다.
    - **[방법 2]:** onnxruntime 기반 라이브러리(fastembed)로 cross-encoder를 교체한다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** onnxruntime 기반 cross-encoder(fastembed), 스레드 수 설정(`threads=8`).
    - **주요 단계:** 콜드로드+fp32+512토큰 조건에서 12.5초 측정 $\rightarrow$ 이 값을 근거로 리랭킹 제외 결정 $\rightarrow$ 이후 측정 조건(콜드로드·입력 길이)이 잘못됐음을 확인 $\rightarrow$ onnxruntime 전환 $\rightarrow$ 스레드 수 튜닝.
    - **결과 도출 및 검증:** PyTorch fp32 2463ms에서 onnxruntime 전환만으로 565ms(4.4배, 정확도 74.2% 동일)까지 줄었고, `threads=8` 설정으로 1187ms에서 949ms로 약 20% 더 줄었다. production 평균은 2137ms에서 1034ms가 됐다.

### 3. 결과 (Results)
- **분석 결과 요약:** 한때 "리랭킹은 12.5초나 걸린다"는 측정 결과로 리랭킹 기능 자체를 검색 파이프라인에서 뺐다. 그 12.5초는 콜드로드(모델 첫 로딩)+fp32+긴 입력(512토큰) 조건에서 잰 값이었는데, 실제로는 onnxruntime+int8+짧은 입력 조건에서 565ms까지 줄일 수 있었다. 측정 조건 하나를 잘못 잡아서 "리랭킹은 못 쓴다"는 결론이 한동안 유지된 셈이다. 이 12.5초는 단순한 착오로 끝나지 않고 스펙 문서에 "리랭킹 제외" 결정으로 공식 기록됐다 — p95 지연 목표를 12배 넘긴다는 이유였다. 이후 웜업을 거친 뒤 짧은 입력 조건으로 onnxruntime을 재검증해 565ms를 확인하고 나서야, 스펙 문서의 그 결정 항목을 개정해 제외 결정 자체를 공식적으로 뒤집을 수 있었다.

### 4. 인사이트 및 액션 (Insights & Action)
- **인사이트 (Insight):** 성능 측정값은 항상 "어떤 조건에서 쟀는지"를 같이 봐야 한다. 콜드로드·정밀도(fp32 vs int8)·입력 길이 중 하나만 실제 운영 조건과 달라도 결론이 완전히 뒤집힌다. "느려서 못 쓴다"는 결론은 기능의 한계가 아니라 측정 조건의 한계였을 수 있다. 게다가 그 결론이 스펙 문서에 공식 결정으로 못박히고 나면, 되돌리는 데는 재측정 결과만으론 부족하고 결정 항목 자체를 개정하는 절차가 한 번 더 필요했다. 잘못된 측정 하나가 공식 결정으로 굳어지는 순간부터 되돌리기 비용이 확 뛴다.
- **실행 방안 (Action Plan):** 성능 문제로 기능을 빼기 전에, 측정값에 콜드로드 여부·정밀도·입력 길이·스레드 수를 명시하고 실제 운영 조건과 비교한다. 조건이 다르면 그 결론은 잠정 보류로 두고 재측정한다.
- **한 줄 결론 (Key Takeaway):** CPU cross-encoder 리랭킹은 onnxruntime 전환과 스레드 튜닝만으로 PyTorch 대비 4배 넘게 빨라졌고, 그전의 "못 쓴다"는 결론은 측정 조건이 잘못됐던 탓이었다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/onnx_rerank_bench.py){: target="_blank"}
- **다음 스텝 (Next Step):** 지금 스레드 튜닝(threads=8)은 특정 서버 코어 수에 맞춘 값이라, 코어 수가 다른 환경에서는 최적값이 달라질 수 있다. 서버 스펙별로 최적 스레드 수를 자동 탐색하는 부분이 남아 있다.
