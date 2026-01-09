import ollama
import yaml
import requests
from pathlib import Path
from src.chat import BaseChatAPI

# 설정 로드
with open(Path(__file__).parent.parent / ".config.yaml") as f:
    config = yaml.safe_load(f)

# Ollama web을 사용하기 위해 api key 필요
API_KEY = config["api"]["ollama"]["key"]
BASE = config.get("api", {}).get("ollama", {}).get("base_url", "http://localhost:11434")

class OllamaWeb(ollama.Ollama):
    def __init__(self, base_url=BASE, api_key=API_KEY):
        if not api_key:
            raise ValueError("Ollama API 키가 설정되지 않았습니다. .config.yaml에 설정하세요.")
        super().__init__(base_url=base_url)
        self.api_key = api_key

    def _check_authorization(self):
        """Authorization header 검증"""
        if not self.api_key or not self.api_key.strip():
            raise ValueError('Authorization header with Bearer token is required for web search')

    def web_search(self, query: str, max_results: int = 3) -> dict:
        """
        웹 검색 수행

        Args:
            query: 검색할 쿼리
            max_results: 반환할 최대 결과 수 (기본값: 3)

        Returns:
            dict: {
                'results': [
                    {
                        'title': '결과 제목',
                        'url': '결과 URL',
                        'content': '결과 내용'
                    },
                    ...
                ]
            }

        Raises:
            ValueError: OLLAMA_API_KEY가 설정되지 않은 경우
        """
        self._check_authorization()

        api_url = "https://ollama.com/api/web_search"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "max_results": max_results
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Web search failed: {str(e)}"}

    def web_fetch(self, url: str) -> dict:
        """
        제공된 URL의 웹 페이지 콘텐츠 가져오기

        Args:
            url: 가져올 웹 페이지 URL

        Returns:
            dict: {
                'title': 페이지 제목,
                'content': 페이지 본문,
                'links': 페이지 내 링크 목록
            }

        Raises:
            ValueError: OLLAMA_API_KEY가 설정되지 않은 경우
        """
        self._check_authorization()

        api_url = "https://ollama.com/api/web_fetch"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {"url": url}

        try:
            response = requests.post(api_url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Web fetch failed: {str(e)}"}


# ============ 사용 예시 ============
if __name__ == "__main__":
    ollama_web = OllamaWeb(api_key=API_KEY, base_url=BASE)

    print("사용 가능 모델:", ollama_web.models())

    # Web search 테스트
    print("\n=== Web Search 테스트 ===")
    search_result = ollama_web.web_search("Python programming best practices", max_results=3)
    if "error" in search_result:
        print(f"에러 발생: {search_result['error']}")
    else:
        results = search_result.get('results', [])
        print(f"검색 결과 개수: {len(results)}")
        for i, result in enumerate(results, 1):
            print(f"\n[{i}] {result.get('title', 'N/A')}")
            print(f"    URL: {result.get('url', 'N/A')}")
            print(f"    내용: {result.get('content', 'N/A')[:100]}...")

    # Web fetch 테스트
    print("\n=== Web Fetch 테스트 ===")
    fetch_result = ollama_web.web_fetch("https://ollama.com")
    if "error" in fetch_result:
        print(f"에러 발생: {fetch_result['error']}")
    else:
        print(f"제목: {fetch_result.get('title', 'N/A')}")
        print(f"콘텐츠 길이: {len(fetch_result.get('content', ''))} 문자")
        print(f"링크 개수: {len(fetch_result.get('links', []))}")

    # Web search + Chat 조합 예시
    print("\n=== Web Search + Chat 조합 ===")
    search_data = ollama_web.web_search("Ollama latest features 2025", max_results=2)
    if "error" not in search_data and ollama_web.models():
        search_summary = "\n".join([
            f"{r.get('title')}: {r.get('content', '')[:200]}"
            for r in search_data.get('results', [])
        ])
        response = ollama_web.chat(
            model=ollama_web.models()[0],
            messages=f"다음 검색 결과를 바탕으로 Ollama의 최신 기능을 요약해줘:\n\n{search_summary}"
        )
        print(f"요약: {response}")
