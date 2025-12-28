# gemini.py
import os
import yaml
import base64
import requests
from pathlib import Path
from src.chat import BaseChatAPI

# 설정 로드
with open(Path(__file__).parent.parent / ".config.yaml") as f:
    config = yaml.safe_load(f)

API_KEY = config["api"]["aistudio"]["key"]
BASE = "https://generativelanguage.googleapis.com/v1beta"


class Gemini(BaseChatAPI):
    _MODEL_PRICES = {
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
            raise ValueError("Gemini API 키가 설정되지 않았습니다. .config.yaml에 설정하세요.")
        self.key = api_key

    @property
    def MODEL_PRICES(self) -> dict:
        return self._MODEL_PRICES

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

    def _convert_to_gemini_format(self, messages: list) -> list:
        """
        표준 OpenAI 형식 메시지를 Gemini 형식으로 변환
        OpenAI: [{"role": "user", "content": "text or list"}]
        Gemini: [{"role": "user", "parts": [{"text": "..."}]}]
        """
        gemini_contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # content가 리스트인 경우 (멀티모달)
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append({"text": item.get("text", "")})
                        elif item.get("type") == "image_url":
                            # 이미지 처리 - Gemini format으로 변환
                            image_url = item.get("image_url", {}).get("url", "")
                            if image_url.startswith("data:image"):
                                # base64 이미지
                                parts.append({
                                    "inline_data": {
                                        "mime_type": "image/jpeg",
                                        "data": image_url.split(",")[1]
                                    }
                                })
                gemini_contents.append({"role": role, "parts": parts if parts else [{"text": ""}]})
            else:
                # 텍스트만
                gemini_contents.append({
                    "role": role,
                    "parts": [{"text": str(content)}]
                })
        return gemini_contents

    # 표준 형식의 메시지로 채팅 수행
    def chat(self, model: str, messages: list | str, temperature=0.7):
        """
        표준 OpenAI 호환 형식의 메시지를 받아 Gemini API로 전송
        """
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        # 표준 형식을 Gemini 형식으로 변환
        gemini_contents = self._convert_to_gemini_format(messages)
        
        url = f"{BASE}/models/{model}:generateContent?key={self.key}"
        payload = {
            "contents": gemini_contents,
            # "generationConfig": {"temperature": temperature}
        }
        r = requests.post(url, json=payload).json()
        try:
            return r["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return str(r)


# ============ 사용 예시 ============
if __name__ == "__main__":
    g = Gemini()

    print("사용 가능 모델:", g.models())

    # 텍스트만 (표준 형식)
    resp = g.chat("gemini-2.5-flash-lite", [
        {"role": "user", "content": "안녕! 오늘 기분 어때?"}
    ])
    print("→", resp)

    # 또는 문자열로 직접 전달
    resp2 = g.chat("gemini-2.5-flash-lite", "안녕! 오늘 기분 어때?")
    print("→", resp2)
