# ollama.py
import os
import yaml
import requests
from pathlib import Path
from src.chat import BaseChatAPI

# 설정 로드
with open(Path(__file__).parent.parent / ".config.yaml") as f:
    config = yaml.safe_load(f)

BASE = config.get("api", {}).get("ollama", {}).get("base_url", "http://localhost:11434")

class Ollama(BaseChatAPI):
    _MODEL_INFO = {
      # Ollama 로컬 모델 추천 (2026년 1월 기준 실제 성능 순위)
      # 기준: Open LLM Leaderboard, LMSYS Arena (오픈 모델 부분), 사용자 피드백, 벤치마크 (MMLU, GPQA, Coding 등)
      # Quantization: Q4_K_M 기본 가정 (메모리 효율 + 품질 균형 최고)

      "qwen3:72b": "최고 성능 (멀티태스크, 다국어, 복잡 추론 최고), 컨텍스트 128K, 메모리 ~40-45GB",
      "deepseek-r1:70b": "추론/코딩/수학 초강자, reasoning 특화, 컨텍스트 128K, 메모리 ~43GB",
      "llama4:70b": "Meta 플래그십, 안정성 + 생태계 강함, 컨텍스트 128K+, 메모리 ~42GB",
      "gemma3:27b": "효율적 고성능, 창의성 + 속도 균형, 컨텍스트 128K, 메모리 ~17GB",
      "qwen3:32b": "압도적 가성비 (70B급 성능 근접), 다국어/장문 처리 강함, 컨텍스트 128K, 메모리 ~18-22GB",
      "deepseek-r1:32b": "코딩/에이전트 특화, 빠른 속도, 컨텍스트 128K, 메모리 ~20GB",
      "phi4:14b": "경량 고지능, Microsoft 최신, 온디바이스/엣지 강함, 컨텍스트 128K, 메모리 ~8-10GB",
      "gemma3:12b": "빠르고 균형 잡힌 중급 모델, 창의적 작업 우수, 컨텍스트 128K, 메모리 ~8GB",
      "qwen3:14b": "16GB RAM 최적, 다국어 + 일반 작업 최고, 컨텍스트 128K, 메모리 ~8-10GB",
      "deepseek-r1:14b": "추론/코딩 특화 중급, 속도 빠름, 컨텍스트 128K, 메모리 ~9GB",

      # 추가 추천 (특화 모델)
      "qwen3-coder:32b": "코딩 전문 최강, 디버깅/리팩토링 우수",
      "gemma3:4b": "초경량 고속, 모바일/엣지 용도",
      "deepseek-v3:7b": "작지만 강력한 reasoning 엔진",
        # 추가 모델은 https://ollama.com/library 참고
    }

    def __init__(self, base_url=BASE):
        self.base_url = base_url.rstrip("/")

    @property
    def MODEL_PRICES(self) -> dict:
        return self._MODEL_INFO

    # 사용 가능한 모든 모델 목록 가져오기
    def models(self):
        url = f"{self.base_url}/api/tags"
        try:
            r = requests.get(url).json()
            return [m["name"] for m in r.get("models", [])]
        except Exception as e:
            return []

    # 표준 형식의 메시지로 채팅 수행
    def chat(self, model: str, messages: list | str, temperature: float = 0.7):
        """Ollama API를 사용한 채팅"""
        url = f"{self.base_url}/api/chat"
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        try:
            r = requests.post(url, json=payload).json()
            return r["message"]["content"]
        except Exception as e:
            return f"Error: {str(e)}"


# ============ 사용 예시 ============
if __name__ == "__main__":
    ollama = Ollama()

    print("사용 가능 모델:", ollama.models())

    # 텍스트만 (표준 형식)
    for model in ollama.models()[:3]:
      resp = ollama.chat(
          model=model,
          messages=[
              {"role": "user", "content": "안녕! 오늘 기분 어때?"}
          ]
      )
      print(model, "→", resp)

      # 또는 문자열로 직접 전달
      resp2 = ollama.chat(
          model=model,
          messages="안녕! 오늘 기분 어때?"
      )
      print(model, "→", resp2)
