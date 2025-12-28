# openrouter.py
import os
import yaml
import base64
import requests
from pathlib import Path
from src.chat import BaseChatAPI

# 설정 로드
with open(Path(__file__).parent.parent / ".config.yaml") as f:
    config = yaml.safe_load(f)

API_KEY = config["api"]["openrouter"]["key"]
BASE = "https://openrouter.ai/api/v1"

class OpenRouter(BaseChatAPI):
    _MODEL_PRICES = {
        # 무료 티어 모델 (2025년 12월 기준 실제 무료 모델)
        "allenai/olmo-3.1-32b-think:free": "무료 ($0/M tokens), 깊은 추론 특화, 컨텍스트 66K",
        "xiaomi/mimo-v2-flash:free": "무료 ($0/M tokens), MoE 309B (15B active), 코딩/추론 강점, 컨텍스트 262K",
        "nvidia/nemotron-3-nano-30b-a3b:free": "무료 ($0/M tokens), 프롬프트/출력 로깅됨 (시험용), 컨텍스트 256K",
        "mistralai/devstral-2512:free": "무료 ($0/M tokens), 에이전트 코딩 특화 123B, 컨텍스트 262K",
        "nex-agi/deepseek-v3.1-nex-n1:free": "무료 ($0/M tokens), 에이전트/툴 사용 특화",
        "arcee-ai/trinity-mini:free": "무료 ($0/M tokens), MoE 26B (128 experts)",
        "tngtech/tng-r1t-chimera:free": "무료 ($0/M tokens), 창작 스토리텔링 특화",
        "allenai/olmo-3-32b-think:free": "무료 ($0/M tokens), 추론/지시 따르기 강점",

        # 인기 유료/저비용 모델 (2025년 기준 인기 모델 예시)
        "google/gemini-3-flash-preview": "저비용 ($0.50/M 입력, $3/M 출력), 멀티모달 (이미지/오디오/비디오), 컨텍스트 1M",
        "openai/gpt-5.2-chat": "입력 $1.75/M / 출력 $14/M, 저지연 채팅 특화",
        "openai/gpt-5.2-pro": "고성능 ($21/M 입력, $168/M 출력), 복잡 작업/장컨텍스트",
        "openai/gpt-5.2": "프론티어급 ($1.75/M 입력, $14/M 출력), 동적 추론",
        "mistralai/mistral-small-creative": "저비용 ($0.10/M 입력, $0.30/M 출력), 창작/롤플레잉 특화",
        # 추가 모델은 https://openrouter.ai/models 또는 rankings 확인
    }

    def __init__(self, api_key=API_KEY):
        if not api_key:
            raise ValueError("OpenRouter API 키가 설정되지 않았습니다. .config.yaml에 설정하세요.")
        self.key = api_key
        self.headers = {
            "Authorization": f"Bearer {self.key}",
            # "HTTP-Referer": "https://your-site.com",
            # "X-Title": "Your App Name",
        }

    @property
    def MODEL_PRICES(self) -> dict:
        return self._MODEL_PRICES

    # 사용 가능한 모든 모델 목록 가져오기 (OpenRouter 전용 엔드포인트)
    def models(self):
        url = f"{BASE}/models"
        r = requests.get(url, headers=self.headers).json()
        return [m["id"] for m in r.get("data", [])]

    # 표준 형식의 메시지로 채팅 수행 (OpenAI 호환)
    def chat(self, model: str, messages: list | str, temperature: float = 0.7):
        """표준 OpenAI 호환 형식의 메시지로 채팅 수행"""
        url = f"{BASE}/chat/completions"
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        r = requests.post(url, json=payload, headers=self.headers).json()
        try:
            return r["choices"][0]["message"]["content"]
        except Exception as e:
            return str(r)


# ============ 사용 예시 ============
if __name__ == "__main__":
    router = OpenRouter()

    print("사용 가능 모델 예시:", router.models()[:20])  # 너무 많아서 20개만 표시

    # 텍스트만 (표준 형식)
    resp = router.chat(
        model="xiaomi/mimo-v2-flash:free",
        messages=[
            {"role": "user", "content": "안녕! 오늘 기분 어때?"}
        ]
    )
    print("→", resp)

    # 또는 문자열로 직접 전달
    resp2 = router.chat(
        model="xiaomi/mimo-v2-flash:free",
        messages="안녕! 오늘 기분 어때?"
    )
    print("→", resp2)
