# subagent.py
import datetime
from typing import Dict, List
from src.chat import get_client


class SubAgent:
    """
    서브 에이전트 클래스: 독립 메시지 히스토리 유지.
    provider와 model을 함께 받아 클라이언트를 결정.
    """
    def __init__(self, name: str, system_prompt: str, provider: str, model: str):
        self.name = name
        self.system_prompt = system_prompt
        self.provider = provider
        self.model = model
        self.client = get_client(provider, model)  # provider와 model로 클라이언트 결정
        self.messages: List[Dict] = [{"role": "system", "content": system_prompt}]

    def chat(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        response = self.client.chat(model=self.model, messages=self.messages)
        self.messages.append({"role": "assistant", "content": response})
        return response

    def reset(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]
        print(f"[{self.name}] 세션 초기화 완료")

class SessionManager:
    """
    메인 세션 매니저: provider와 model을 함께 설정.
    서브 에이전트 관리 및 채팅.
    """
    def __init__(self, provider: str = "gemini", default_model: str = "gemini-1.5-flash"):
        """
        Args:
            provider: 프로바이더명 ('gemini' 또는 'openrouter')
            default_model: 기본 모델명 (예: 'gemini-1.5-flash', 'xiaomi/mimo-v2-flash:free')
        """
        self.provider = provider
        self.default_model = default_model
        self.client = get_client(provider, default_model)  # provider와 model로 클라이언트 결정
        
        self.sub_agents: Dict[str, SubAgent] = {}
        self.main_messages: List[Dict] = []
        print(f"[{datetime.datetime.now()}] SessionManager 초기화 완료. provider={provider}, 모델={default_model}")

    def create_subagent(self, name: str, description: str, system_prompt: str, provider: str = None, model: str = None) -> SubAgent:
        """
        서브 에이전트 생성
        
        Args:
            name: 에이전트 이름
            description: 에이전트 설명 (역할)
            system_prompt: 시스템 프롬프트
            provider: 사용할 프로바이더명 (None일 경우 기본값 사용)
            model: 사용할 모델명 (None일 경우 기본 모델 사용)
        
        Returns:
            SubAgent 인스턴스
        """
        full_prompt = f"You are an expert sub-agent specializing in '{description}'.\n{system_prompt}"
        selected_provider = provider or self.provider
        selected_model = model or self.default_model
        agent = SubAgent(name=name, system_prompt=full_prompt, provider=selected_provider, model=selected_model)
        self.sub_agents[name] = agent
        print(f"[{datetime.datetime.now()}] 서브 에이전트 '{name}' 생성 완료 ({description}, provider={selected_provider}, 모델={selected_model})")
        return agent

    def call_subagent(self, name: str, prompt: str) -> str:
        if name not in self.sub_agents:
            raise ValueError(f"서브 에이전트 '{name}'가 존재하지 않습니다.")
        print(f"[{datetime.datetime.now()}] [{name}] 호출 시작: {prompt[:100]}...")
        response = self.sub_agents[name].chat(prompt)
        print(f"[{datetime.datetime.now()}] [{name}] 응답 완료:\n{response}\n")
        return response

    def main_chat(self, prompt: str) -> str:
        self.main_messages.append({"role": "user", "content": prompt})
        print(f"[{datetime.datetime.now()}] 메인 채팅 호출: {prompt[:100]}...")
        response = self.client.chat(model=self.default_model, messages=self.main_messages)
        self.main_messages.append({"role": "assistant", "content": response})
        print(f"[{datetime.datetime.now()}] 메인 응답:\n{response}\n")
        return response

# 사용 예시
if __name__ == "__main__":
    print("서브 에이전트 시스템 테스트 시작 (모델명으로 자동 선택)\n")
    try:
        # 기본 모델로 SessionManager 초기화 (get_client가 자동으로 Gemini 사용)
        # manager = SessionManager(default_model="gemini-2.5-flash-lite")
        # 또는 OpenRouter 모델 사용:
        manager = SessionManager(provider='openrouter', default_model="xiaomi/mimo-v2-flash:free")

        python_coder = manager.create_subagent(
            name="python_coder",
            description="Python 코드 작성 및 리팩토링 전문가",
            system_prompt="""You are a senior Python developer specializing in clean, idiomatic Python 3.11+ code.
When invoked:
1. Understand the requirement clearly.
2. Write or refactor code with type hints, docstrings, and best practices.
3. Explain changes briefly.
Focus on simplicity, readability, and error handling.
답변은 한글로 해주세요."""
        )

        test_runner = manager.create_subagent(
            name="test_runner",
            description="Python 테스트 작성 전문가",
            system_prompt="""You are a Python testing expert using pytest.
Write comprehensive tests and report results.
답변은 한글로 해주세요."""
        )

        code_reviewer = manager.create_subagent(
            name="code_reviewer",
            description="Python 코드 리뷰 전문가",
            system_prompt="""You are a strict Python code reviewer.
Check for bugs, style, performance and suggest improvements.
답변은 한글로 해주세요."""
        )

        manager.call_subagent("python_coder", "FastAPI로 간단한 TODO 리스트 API를 만들어주세요. (GET /todos, POST /todos)")

        manager.call_subagent("test_runner", "위에서 생성된 FastAPI TODO 코드에 대해 pytest 테스트를 작성해주세요.")

        manager.call_subagent("code_reviewer", "위 FastAPI TODO 코드 전체를 리뷰해주세요.")

        print("테스트 완료!")

    except Exception as e:
        print(f"\n오류 발생: {e}")
        print("gemini.py 또는 openrouter.py 확인, API 키 설정 필요.")
