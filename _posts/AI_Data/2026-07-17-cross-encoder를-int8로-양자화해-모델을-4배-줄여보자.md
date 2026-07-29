---
title: cross-encoder를 int8로 양자화해 모델을 4배 줄여보자
description: ONNX cross-encoder 리랭커를 int8 동적 양자화했더니 크기는 1/4로 줄고 속도는 빨라졌는데, 정확도는 오히려 떨어졌다
author: taewony
date: 2026-07-17 23:14:07 +0900
categories: [Quick, AI/Data]
tags: [quantization, int8, cross-encoder, onnx, inference, rerank]
pin: false
math: false
mermaid: false
---

## cross-encoder를 int8로 양자화해 모델을 4배 줄여보자
ONNX로 변환한 cross-encoder 리랭커도 1GB가 넘어 배포·로딩이 무거웠다. int8 동적 양자화로 크기와 속도는 확실히 줄였는데, 그 대가로 정확도를 내줬다.

### 1. 서론 (Introduction)
- **문제/상황 (Problem):** 검색 결과를 다시 정렬하는 cross-encoder 리랭커를 ONNX로 변환해 배포했는데, 모델 하나가 1GB를 넘어 로딩·배포 비용이 컸다.
- **목적 (Purpose):** 동적 int8 양자화로 크기·속도를 얼마나 줄일 수 있는지, 그 대가로 정확도를 얼마나 내주는지 같은 조건에서 실측한다.
- **대상 (Target Audience):** 리랭킹처럼 온프레미스에 ONNX 모델을 올려두고 지연시간·메모리를 신경 써야 하는 개발자.

### 2. 방법 및 과정 (Methods & Process)
- **배경 조사 및 데이터 (Data Collection):** 같은 평가셋으로 fp32와 int8을 각각 돌려 세 지표를 비교했다.

  | 지표 | fp32 | int8 |
  |---|---|---|
  | 정확도 | 83.9% | 77.4% (-6.5%p) |
  | 추론 시간 | 1034ms | 741~781ms (약 28% 빠름) |
  | 모델 크기 | 1.11GB | 0.28GB (1/4) |

- **접근 방법 (Approach Methods):**
    - **[방법 1]:** `onnxruntime.quantization.quantize_dynamic`으로 가중치를 8bit 정수로 바꾸는 동적(post-training) 양자화를 적용한다. 별도 캘리브레이션 데이터셋 없이 바로 적용할 수 있다.
    - **[방법 2]:** 정확도 저하를 감수하기 어려운 경우를 대비해, 환경변수 플래그 하나로 fp32/int8을 런타임에 선택할 수 있게 남겨둔다(예: `RERANK_QUANTIZE=0`이면 fp32로 복귀). 이 플래그는 처음엔 기본값을 fp32로 두고 int8은 켜고 싶을 때만 켜는 옵트인으로만 열어뒀다가, 실제 운영에서 속도·메모리 부담을 확인한 뒤에야 기본값을 int8로 전환했다.
- **분석 및 해결 프로세스 (Analysis Flow):**
    - **도구/기술:** `onnxruntime`, `onnxruntime.quantization.quantize_dynamic(weight_type=QInt8)`.
    - **주요 단계:** fp32 ONNX 모델 로드 $\rightarrow$ `quantize_dynamic` 적용 $\rightarrow$ 같은 평가셋으로 fp32/int8의 정확도·속도·크기 비교 $\rightarrow$ 기본값 결정.
    - **결과 도출 및 검증:** 크기는 1.11GB에서 0.28GB로 1/4, 추론 시간은 1034ms에서 741~781ms로 약 28% 줄었다. 대신 정확도는 83.9%에서 77.4%로 6.5%p 떨어졌다.

### 3. 결과 (Results)
- **분석 결과 요약:** "성능이 28% 좋아졌다"는 표현은 속도 얘기이지 정확도 얘기가 아니다. 정확도만 따로 보면 오히려 나빠졌다. 크기·속도·정확도 세 지표가 서로 다른 방향으로 움직인 셈이다.

### 4. 인사이트 및 액션 (Insights & Action)
- **인사이트 (Insight):** 이 리랭커는 최종 판단이 아니라 1차 후보군을 좁혀주는 역할이다. 그래서 6.5%p의 정확도 손실보다 크기·속도 이득이 이 위치에서는 더 크다고 판단해 int8을 기본값으로 채택했다. "수치가 좋아졌다"를 볼 때는 그게 어떤 지표인지 반드시 구분해야 한다. 리스크 있는 트레이드오프를 처음부터 기본값으로 밀어붙이지 않고 먼저 옵션으로 넣어 부담을 확인한 다음, 확신이 설 때 기본값으로 승격하는 순서가 안전했다.
- **실행 방안 (Action Plan):** 정확도가 그대로 최종 결과가 되는 단계(예: 순위 확정, 최종 판단)에는 fp32를 유지하고, 리랭킹처럼 손실을 뒤에서 흡수할 수 있는 단계에만 int8을 적용한다. 되돌릴 수 있는 스위치는 항상 남겨둔다.
- **한 줄 결론 (Key Takeaway):** 크기·속도가 좋아 보여도 정확도까지 같이 좋아진 건 아니었다. 어떤 트레이드오프를 감수하는지 스스로 알고 채택해야 한다. [샘플 코드](https://github.com/TaewonyNet/taewonynet.github.io/blob/master/src/onnx_int8_quantize_compare.py){: target="_blank"}
- **다음 스텝 (Next Step):** 동적 양자화 대신 캘리브레이션 데이터셋을 쓰는 정적(static) 양자화나, int8보다 손실이 적다고 알려진 fp16 변환을 같은 평가셋에 시도해 정확도 손실 폭을 더 줄일 수 있는지가 남은 과제다.
