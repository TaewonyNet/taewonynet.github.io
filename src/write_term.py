import sys
import json
import re
import os

import requests

from gemini import Gemini


def analyze_text(text_content):
    prompt_template = """
당신은 20년차 IT 강사이자 베테랑 개발자이며, 동시에 대학 신입생에게도 설명할 수 있을 만큼 쉽게 풀어내는 전문가입니다.
사용자가 입력하는 모든 문장 속 개발·IT·비즈니스·실무 전문 용어를 100% 찾아 다음 규칙만 정확히 지켜서 정리해주세요.

### 출력 형식 (이 구조만 딱 나오게 해주세요)
```json
{
    "영어 풀네임(camel case)": {
        "term": "[약어/원어]",
        "korean_full": "한글 풀네임",
        "english_full": "영어 풀네임(camel case)",
        "definition": "전문적인 원문 정의 1~2문장",
        "easy_meaning": "대학 신입생도 이해할 수 있는 한 문장 설명",
        "analogy": "일상 비유 또는 실제 예시 하나",
        "difficulty": "★☆☆☆☆ ~ ★★★★★",
        "related_keywords": ["키워드1", "키워드2", "키워드3"]
    }
},
...
```

### 추가 규칙
- 모르는 용어는 진행하지 않으며 무시
- JSON KEY:VALUE 형태로 결과만 출력
- 요약 문장, 인사말, 마무리 멘트 등 불필요한 말은 절대 추가 금지
- 모든 출력은 평서문으로 감탄사, 의성어 사용 금지
- 완전히 JSON으로 파싱 될 수 있는지 검증 필수

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


def analyze_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at '{file_path}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    return analyze_text(file_content)


def analyze_directory(base_path, json_path, excluded_dirs=None):
    excluded_dirs = [d or '.' for d in excluded_dirs or []]

    # Load existing data if JSON file exists
    result_data = {
        "complete": [],
        "term": {}
    }
    print(f"Starting analysis in directory: {os.path.abspath(base_path)}\n")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
            print(f"✓ Loaded existing data from {json_path}")
            print(f"  - Already processed files: {len(result_data.get('complete', []))}")
            print(f"  - Existing terms: {len(result_data.get('term', {}))}\n")
        except Exception as ex:
            print(f"⚠ Warning: Could not load existing JSON: {ex}\n", file=sys.stderr)

    processed_files = result_data.get("complete", [])
    new_files_count = 0

    for root, dirs, files in os.walk(base_path):
        if os.path.relpath(root, base_path) not in excluded_dirs:
            for file_name in files:
                file_path = os.path.join(root, file_name)

                if file_path in processed_files:
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        file_content = file.read()

                    file_split = file_content.split('---')
                    if len(file_split) > 3:
                        file_content = '---'.join(file_split[2:]).strip()

                    analysis_result = analyze_text(file_content)
                    cleaned_result = re.sub(
                        r'^```(?:json)?\s*|\s*```$', '', analysis_result.strip(), flags=re.MULTILINE
                    )

                    parsed_result = json.loads(cleaned_result)

                    if isinstance(parsed_result, dict):
                        result_data["term"].update(parsed_result)

                    result_data["complete"].append(file_path)
                    new_files_count += 1
                    print(f"✓ Completed: {file_path}")

                except Exception as ex:
                    print(f"✗ Error processing file {file_path}: {ex}", file=sys.stderr)

    # Save result to JSON file
    try:
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)
        print(f"\n✓ Results saved to {json_path}")
        print(f"  - New files processed: {new_files_count}")
        print(f"  - Total processed files: {len(result_data['complete'])}")
        print(f"  - Total terms: {len(result_data['term'])}")
    except Exception as ex:
        print(f"Error saving JSON file {json_path}: {ex}", file=sys.stderr)


if __name__ == "__main__":
    base_path = "../_posts"
    json_path = "data/term.json"
    excluded_dirs = {".ipynb_checkpoints", "Architecture", "Diary", "Movie", ""}
    analyze_directory(base_path, json_path, excluded_dirs)

    # file_path = "../_posts/AI_Data/2025-12-09-Google-Gemini를-사용해보자.md"
    # analyze_file(file_path)
