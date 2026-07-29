"""
가장 단순한 북마크릿 — 원리 데모.

JS_CODE는 현재 페이지의 title을 console.log로 출력하는 최소 스니펫이다.
build_bookmarklet_url()이 이를 `javascript:` URL로 인코딩한다. 즐겨찾기의
URL 칸에 이 결과를 붙여넣으면 북마크릿이 완성된다.
"""

from urllib.parse import quote

JS_CODE = """
(function () {
    console.log("현재 페이지 title:", document.title);
})();
""".strip()


def build_bookmarklet_url(js_code: str) -> str:
    """JS 코드 문자열을 즐겨찾기에 저장 가능한 javascript: URL로 변환한다."""
    encoded = quote(js_code, safe="")
    return f"javascript:{encoded}"


def main() -> None:
    url = build_bookmarklet_url(JS_CODE)
    print("원본 JS:")
    print(JS_CODE)
    print(f"\n북마크릿 URL 길이: {len(url)}자")
    print(f"URL 앞부분: {url[:60]}...")
    assert url.startswith("javascript:")
    print("\n검증 통과: javascript: 접두사로 시작하는 URL 생성 확인")


if __name__ == "__main__":
    main()
