# gemini.py
import os
import yaml
import base64
import requests
from pathlib import Path

# 설정 로드
with open(Path(__file__).parent.parent / ".config.yaml") as f:
    config = yaml.safe_load(f)

API_KEY = config["api"]["aistudio"]["key"]
BASE = "https://generativelanguage.googleapis.com/v1beta"


class Gemini:
    MODEL_PRICES = {
        "gemini-2.5-pro": "무료 입력/출력 (표준) | 유료: 입력 $1.25(~200K)/$2.50(>200K), 출력 $10.00/~$15.00",
        "gemini-2.5-flash": "무료 입력/출력 (표준) | 유료: 입력 $0.30(텍스트/이미지/비디오)/$1.00(오디오), 출력 $2.50",
        "gemini-2.5-flash-preview-09-2025": "무료 입력/출력 (표준) | 유료: 입력 $0.30(텍스트/이미지/비디오)/$1.00(오디오), 출력 $2.50",
        "gemini-2.5-flash-lite": "무료 입력/출력 (표준) | 유료: 입력 $0.10(텍스트/이미지/비디오)/$0.30(오디오), 출력 $0.40",
        "gemini-2.5-flash-lite-preview-09-2025": "무료 입력/출력 (표준) | 유료: 입력 $0.10(텍스트/이미지/비디오)/$0.30(오디오), 출력 $0.40",
        "gemini-2.5-flash-native-audio-preview-09-2025": "무료 입력/출력 | 유료: 입력 $0.50(텍스트)/$3.00(오디오/비디오), 출력 $2.00(텍스트)/$12.00(오디오)",
        "gemini-2.5-flash-preview-tts": "무료 입력/출력 | 유료: 입력 $0.50(텍스트), 출력 $10.00(오디오)",
        "gemini-2.0-flash": "무료 입력/출력 (표준) | 유료: 입력 $0.10(텍스트/이미지/비디오)/$0.70(오디오), 출력 $0.40",
        "gemini-2.0-flash-lite": "무료 입력/출력 (표준) | 유료: 입력 $0.075, 출력 $0.30",
        "gemini-embedding-001": "무료 입력 (표준) | 유료: 입력 $0.15",
        "gemini-robotics-er-1.5-preview": "무료 입력/출력 | 유료: 입력 $0.30(텍스트/이미지/비디오)/$1.00(오디오), 출력 $2.50",
        "gemma-3": "무료 입력/출력/캐싱 | 유료: 없음",
        "gemma-3n": "무료 입력/출력/캐싱 | 유료: 없음"
    }
    def __init__(self, api_key=API_KEY):
        if not api_key:
            raise ValueError("OpenRouter API 키가 설정되지 않았습니다. .config.yaml 또는 환경변수 OPENROUTER_API_KEY에 설정하세요.")
        self.key = api_key
        self.key = api_key


    # 모든 모델 목록 가져오기
    def models(self):
        url = f"{BASE}/models"
        params = {"key": self.key}
        models = []
        while True:
            r = requests.get(url, params=params).json()
            models.extend(r.get("models", []))
            token = r.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token
        return [m["name"].split("/")[-1] for m in models]

    def model_price(self, model: str):
        return self.MODEL_PRICES.get(model, "모델 가격 정보가 없습니다.")

    def model_price_all(self):
        return self.MODEL_PRICES

    # 텍스트 채팅
    def chat(self, model: str, messages: list | str, temperature=0.7):
        url = f"{BASE}/models/{model}:generateContent?key={self.key}"
        payload = {
            "contents": messages
            if isinstance(messages, list)
            else [{"role": "user", "parts": [{"text": messages}]}],
            # "generationConfig": {"temperature": temperature}
        }
        r = requests.post(url, json=payload).json()
        try:
            return r["candidates"][0]["content"]["parts"][0]["text"]
        except:
            return str(r)

    # 이미지 + 텍스트 채팅
    def vision(self, model: str, prompt: str, images: list):
        def to_b64(path_or_bytes):
            if isinstance(path_or_bytes, (str, Path)):
                with open(path_or_bytes, "rb") as f:
                    data = f.read()
            else:
                data = path_or_bytes
            return base64.b64encode(data).decode()

        parts = [{"text": prompt}]
        for img in images:
            b64 = to_b64(img)
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b64}})

        return self.chat(model, [{"role": "user", "parts": parts}])

# ============ 사용 예시 ============
if __name__ == "__main__":
    g = Gemini()

    print("사용 가능 모델:", g.models())

    # 텍스트만
    resp = g.chat("gemini-2.5-flash-lite", [
        {"role": "user", "parts": [{"text": "안녕! 오늘 기분 어때?"}]}
    ])
    print("→", resp)

    # 이미지 + 텍스트 (주석 해제 후 사용)
    # resp2 = g.vision(
    #     model="gemini-1.5-flash",
    #     prompt="이 사진에 뭐가 있나요?",
    #     images=["./cat.jpg"]
    # )
    # print("→", resp2)
