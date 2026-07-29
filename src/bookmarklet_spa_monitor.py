"""
북마크릿 SPA 페이지 전환 감시 — history.pushState 몽키패치.

JS_BOOKMARKLET_SPA_MONITOR는 history.pushState/replaceState를 감싸
호출될 때마다 커스텀 이벤트(locationchange)를 발생시키고, 리스너가
Beacon으로 URL 변경을 서버에 전송하는 북마크릿이다. 브라우저 없이는
직접 실행할 수 없으므로, 이 파일은 문자열 구조를 정적으로 검증한다 —
필수 API 호출이 모두 포함됐는지, 괄호가 짝이 맞는지 확인한다.
"""

JS_BOOKMARKLET_SPA_MONITOR = """
(function () {
    function wrap(method) {
        var original = history[method];
        return function () {
            var result = original.apply(this, arguments);
            window.dispatchEvent(new Event("locationchange"));
            return result;
        };
    }
    history.pushState = wrap("pushState");
    history.replaceState = wrap("replaceState");

    window.addEventListener("locationchange", function () {
        var payload = JSON.stringify({ url: location.href, ts: Date.now() });
        navigator.sendBeacon("http://127.0.0.1:PORT/collect", payload);
        console.log("페이지 전환 감지:", location.href);
    });

    console.log("SPA 전환 감시 설치 완료");
})();
""".strip()

REQUIRED_APIS = [
    "history.pushState",
    "history.replaceState",
    "dispatchEvent",
    "addEventListener",
    "sendBeacon",
]


def validate_js_structure(js_code: str, required_apis: list[str]) -> list[str]:
    """필수 API 호출 포함 여부와 괄호 짝을 검사해 누락 목록을 반환한다."""
    missing = [api for api in required_apis if api not in js_code]

    balance = 0
    for ch in js_code:
        if ch == "(":
            balance += 1
        elif ch == ")":
            balance -= 1
    if balance != 0:
        missing.append(f"괄호 불균형(diff={balance})")

    return missing


def main() -> None:
    js = JS_BOOKMARKLET_SPA_MONITOR.replace("PORT", "5000")
    missing = validate_js_structure(js, REQUIRED_APIS)

    print(f"검사 대상 API: {REQUIRED_APIS}")
    if missing:
        print(f"검증 실패 — 누락/오류: {missing}")
    else:
        print("검증 통과: 필수 API 전부 포함, 괄호 짝 일치")

    assert not missing


if __name__ == "__main__":
    main()
