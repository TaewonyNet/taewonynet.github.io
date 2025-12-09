from src.gemini import Gemini
import os
import yaml
import base64
import requests
from pathlib import Path


with open(Path(__file__).parent.parent / ".config.yaml") as f:
    config = yaml.safe_load(f)

MODELS = {
    'gemini': {
        'models': {
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
        },
        'client': Gemini(api_key=config["api"]["aistudio"]["key"]),
    }
}
MODELS_DICT = {name:info['client'] for provider, info in MODELS.items() for name in info['models']}

def chat(model: str='gemini-2.5-flash-lite', messages: list | str=None):
    """지정된 모델로 채팅을 수행합니다."""
    client = MODELS_DICT.get(model)
    if client:
        return client.chat(model, messages)
    else:
        raise ValueError(f"지원되지 않는 모델: {model}")


if __name__ == "__main__":
    reqs = chat('gemini-2.5-flash-lite', '안녕하세요')
    print(reqs)
