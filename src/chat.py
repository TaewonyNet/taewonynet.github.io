import os
import yaml
import base64
import requests
from pathlib import Path
from abc import ABC, abstractmethod

# 설정 로드
with open(Path(__file__).parent.parent / ".config.yaml") as f:
    config = yaml.safe_load(f)


class BaseChatAPI(ABC):
    """Chat API의 기본 추상 클래스 - OpenAI 호환 메시지 형식 사용"""

    @abstractmethod
    def __init__(self, api_key: str):
        """API 키 초기화"""
        pass

    @property
    @abstractmethod
    def MODEL_PRICES(self) -> dict:
        """모델 가격 정보 반환"""
        pass

    @abstractmethod
    def models(self) -> list:
        """사용 가능한 모델 목록 반환"""
        pass

    def model_price(self, model: str) -> str:
        """특정 모델의 가격 정보 반환"""
        return self.MODEL_PRICES.get(model, "모델 가격 정보가 없습니다.")

    def model_price_all(self) -> dict:
        """모든 모델의 가격 정보 반환"""
        return self.MODEL_PRICES

    @abstractmethod
    def chat(self, model: str, messages: list | str, temperature: float = 0.7) -> str:
        """
        표준 형식의 메시지로 채팅 수행
        messages: [{"role": "user", "content": "..."}, ...] 또는 문자열
        """
        pass

    def vision(self, model: str, prompt: str, images: list) -> str:
        """이미지 + 텍스트 채팅 (표준 OpenAI 호환 형식)"""
        def to_b64(path_or_bytes):
            if isinstance(path_or_bytes, (str, Path)):
                with open(path_or_bytes, "rb") as f:
                    data = f.read()
            else:
                data = path_or_bytes
            return base64.b64encode(data).decode()

        content = [{"type": "text", "text": prompt}]
        for img in images:
            b64 = to_b64(img)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })

        messages = [{"role": "user", "content": content}]
        return self.chat(model, messages)


# 지원하는 프로바이더
SUPPORTED_PROVIDERS = ["gemini", "openrouter"]

def validate_provider(provider: str) -> None:
    """프로바이더명 검증
    
    Args:
        provider: 프로바이더명 ('gemini' 또는 'openrouter')
    
    Raises:
        ValueError: 지원되지 않는 프로바이더인 경우
    """
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(f"지원되지 않는 프로바이더: {provider}. 지원: {SUPPORTED_PROVIDERS}")


# 클라이언트 초기화
def _init_clients():
    """클라이언트들을 지연 로딩으로 초기화"""
    from src.gemini import Gemini
    from src.openrouter import OpenRouter
    
    clients = {}
    try:
        clients['gemini'] = Gemini(api_key=config["api"]["aistudio"]["key"])
    except Exception as e:
        print(f"Gemini 초기화 실패: {e}")
    
    try:
        clients['openrouter'] = OpenRouter(api_key=config["api"]["openrouter"]["key"])
    except Exception as e:
        print(f"OpenRouter 초기화 실패: {e}")
    
    return clients


# 전역 클라이언트 캐시
_CLIENTS_CACHE = None


def get_client(provider: str, model: str) -> BaseChatAPI:
    """프로바이더와 모델로 클라이언트 반환
    
    Args:
        provider: 프로바이더명 ('gemini' 또는 'openrouter')
        model: 모델명 (예: 'gemini-2.5-flash-lite', 'xiaomi/mimo-v2-flash:free')
    
    Returns:
        BaseChatAPI 인스턴스 (Gemini 또는 OpenRouter)
    
    Raises:
        ValueError: 지원되지 않는 프로바이더인 경우
    """
    validate_provider(provider)
    
    global _CLIENTS_CACHE
    if _CLIENTS_CACHE is None:
        _CLIENTS_CACHE = _init_clients()
    
    print(f"[get_client] provider={provider}, model={model}")
    
    if provider == "gemini":
        return _CLIENTS_CACHE.get('gemini')
    elif provider == "openrouter":
        return _CLIENTS_CACHE.get('openrouter')
    else:
        raise ValueError(f"지원되지 않는 프로바이더: {provider}")


def chat(model: str, provider: str, messages: list | str = None, temperature: float = 0.7) -> str:
    """지정된 프로바이더와 모델로 채팅을 수행합니다.
    
    Args:
        model: 모델명 (예: 'gemini-2.5-flash-lite', 'xiaomi/mimo-v2-flash:free')
        provider: 프로바이더명 ('gemini' 또는 'openrouter')
        messages: 메시지 리스트 또는 문자열
        temperature: 응답의 창의성 (0.0~1.0)
    
    Returns:
        모델의 응답 텍스트
    
    Raises:
        ValueError: provider가 유효하지 않거나 messages가 None인 경우
    """
    if messages is None:
        raise ValueError("messages 인자가 필수입니다.")
    
    validate_provider(provider)
    
    client = get_client(provider, model)
    if not client:
        raise ValueError(f"클라이언트 초기화 실패: {provider}")
    
    return client.chat(model, messages, temperature)


if __name__ == "__main__":
    result = chat('gemini-2.5-flash-lite', 'gemini', '안녕하세요')
    print(result)
