"""OpenAI 호환 /v1/chat/completions 하나 뒤에 여러 LLM 더미 provider를 라우팅하는 최소 게이트웨이.

실제 API 키 없이도 데모 provider(고정 응답)로 동작 확인이 가능하다.
uvicorn 없이 함수 호출만으로도 라우팅 로직을 검증할 수 있게 TestClient를 사용한다.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]


class ILLMProvider(ABC):
    """모든 provider adapter가 구현해야 하는 공통 인터페이스."""

    @abstractmethod
    def supports(self, model: str) -> bool:
        """이 provider가 해당 모델명을 처리할 수 있는지 여부."""

    @abstractmethod
    def generate(self, model: str, messages: list[ChatMessage]) -> str:
        """모델과 메시지를 받아 응답 텍스트를 반환한다."""


class GeminiDemoProvider(ILLMProvider):
    """Gemini 계열 모델명을 처리하는 데모 provider. 고정 응답을 반환한다."""

    def supports(self, model: str) -> bool:
        return model.startswith("gemini")

    def generate(self, model: str, messages: list[ChatMessage]) -> str:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return f"[gemini-demo:{model}] 받은 질문: {last_user[:40]}"


class GroqDemoProvider(ILLMProvider):
    """Groq 계열 모델명을 처리하는 데모 provider. 고정 응답을 반환한다."""

    def supports(self, model: str) -> bool:
        return model.startswith("groq") or model.startswith("llama")

    def generate(self, model: str, messages: list[ChatMessage]) -> str:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return f"[groq-demo:{model}] 받은 질문: {last_user[:40]}"


class CerebrasDemoProvider(ILLMProvider):
    """Cerebras 계열 모델명을 처리하는 데모 provider. 고정 응답을 반환한다."""

    def supports(self, model: str) -> bool:
        return model.startswith("cerebras")

    def generate(self, model: str, messages: list[ChatMessage]) -> str:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return f"[cerebras-demo:{model}] 받은 질문: {last_user[:40]}"


class Router:
    """요청의 model 필드를 보고 등록된 provider 중 하나로 라우팅한다."""

    def __init__(self, providers: list[ILLMProvider]) -> None:
        self._providers = providers

    def route(self, request: ChatCompletionRequest) -> dict[str, Any]:
        for provider in self._providers:
            if provider.supports(request.model):
                logger.info("routed model=%s -> %s", request.model, type(provider).__name__)
                text = provider.generate(request.model, request.messages)
                return self._to_openai_response(request.model, text)
        raise HTTPException(status_code=400, detail=f"no provider supports model={request.model}")

    @staticmethod
    def _to_openai_response(model: str, text: str) -> dict[str, Any]:
        return {
            "id": "chatcmpl-demo",
            "object": "chat.completion",
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop",
                }
            ],
        }


def build_app(router: Router) -> FastAPI:
    app = FastAPI(title="mini-llm-gateway")

    @app.post("/v1/chat/completions")
    def chat_completions(req: ChatCompletionRequest) -> dict[str, Any]:
        return router.route(req)

    return app


def default_router() -> Router:
    return Router([GeminiDemoProvider(), GroqDemoProvider(), CerebrasDemoProvider()])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    from fastapi.testclient import TestClient

    app = build_app(default_router())
    client = TestClient(app)

    demo_requests = [
        {"model": "gemini-2.5-flash", "messages": [{"role": "user", "content": "라우팅 테스트 1"}]},
        {"model": "groq-llama3-70b", "messages": [{"role": "user", "content": "라우팅 테스트 2"}]},
        {"model": "cerebras-llama3.1-8b", "messages": [{"role": "user", "content": "라우팅 테스트 3"}]},
    ]

    for payload in demo_requests:
        resp = client.post("/v1/chat/completions", json=payload)
        print(resp.status_code, resp.json()["choices"][0]["message"]["content"])

    # 지원하지 않는 모델은 400
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "unknown-model", "messages": [{"role": "user", "content": "x"}]},
    )
    print(resp.status_code, resp.json())
