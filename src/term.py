import requests

from gemini import Gemini


def extract_term(text_content):
    prompt_template = """
당신은 20년차 IT 강사이자 베테랑 개발자이며, 동시에 대학 신입생에게도 설명할 수 있을 만큼 쉽게 풀어내는 전문가입니다.
사용자가 입력하는 모든 문장 속 개발·IT·비즈니스·실무 전문 용어를 100% 찾아 다음 규칙만 정확히 지켜서 정리해주세요.

### 출력 형식 (이 구조만 딱 나오게 해주세요)
```
[
    {
        "[약어/원어]": {
          "term": "[약어/원어]",
          "korean_full": "한글 풀네임",
          "english_full": "영어 풀네임",
          "definition": "전문적인 원문 정의 1~2문장",
          "easy_meaning": "대학 신입생도 이해할 수 있는 한 문장 설명",
          "analogy": "일상 비유 또는 실제 예시 하나",
          "difficulty": "★☆☆☆☆ ~ ★★★★★",
          "related_keywords": ["키워드1", "키워드2", "키워드3"]
        }
    },
    ...
]
```

### 추가 규칙
- 모르는 용어는 솔직히 “이건 ~회사 내부 약어로 보이며 정확한 뜻은 추가 맥락 필요”라고 말하기
- 사용자가 “레벨 1”~“레벨 5” 쓰면 그 수준으로 쉬운 말 강도 조절 (기본 레벨 2~3)
- ARRAY JSON 형태로 결과만 출력
- 요약 문장, 인사말, 마무리 멘트 등 불필요한 말은 절대 추가 금지
- 모든 출력은 평서문으로 어미(~한다., ~해보자., ~하자.)로 감탄사, 의성어 사용 금지

지금부터 이 규칙만 100% 지켜주세요.

---
아래는 분석할 텍스트입니다.
---

"""
    try:
        g = Gemini()
        prompt = prompt_template + text_content
        resp = g.chat(
          "gemini-2.5-flash-lite", [{"role": "user", "parts": [{"text": prompt}]}]
        )
        return resp

    except requests.exceptions.RequestException as e:
        return f"Error calling Gemini API: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"


if __name__ == "__main__":
    text = """
## pandas vs polars
pandas와 polars가 실제 얼마나 차이나는지 정량적으로 평가하기 위한 벤치마크 테스트한다.

### 1. 서론 (Introduction)
- **문제/상황 (Problem):**
    - polars가 버전업이 되면서 실제 사용 가능한 수준으로 올라갔다고 한다.
    - 실제 pandas와 비교하여 성능이 얼마나 차이가 나는지 실제 데이터가 동일하게 나오는지 정량적 분석이 필요하다.
- **목적 (Purpose):**
    - 동일 조건에서 pandas와 polars의 연산을 비교하여 실무 적용을 위한 기준을 확보한다.
- **대상 (Target Audience):**
    - spark를 사용하기에는 아쉽고 pandas를 사용하기엔 너무 느린다는 대부분의 사용자.
    """
    print(extract_term(text))
