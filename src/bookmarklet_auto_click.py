"""
북마크릿 요소 클릭 자동화 — 셀렉터 후보 순회.

JS_BOOKMARKLET_AUTO_CLICK은 셀렉터 후보 목록을 순서대로 시도해 처음
매칭되는 요소에 MouseEvent('click')을 dispatchEvent로 발생시키는
북마크릿이다. try_selectors()는 같은 "후보 순회 → 첫 매칭 채택" 로직을
파이썬 쪽에서 재현한 헬퍼로, 실제 DOM 대신 가짜 페이지(dict)로 검증한다.
"""

from collections.abc import Callable

JS_BOOKMARKLET_AUTO_CLICK = """
(function () {
    var candidates = ["#submit-btn", ".btn-primary", "button[type=submit]"];
    var target = null;
    for (var i = 0; i < candidates.length; i++) {
        target = document.querySelector(candidates[i]);
        if (target) break;
    }
    if (!target) {
        console.warn("클릭 대상을 찾지 못함");
        return;
    }
    target.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    console.log("클릭 발생:", target);
})();
""".strip()


def try_selectors(selectors: list[str], exists_fn: Callable[[str], bool]) -> str | None:
    """셀렉터 후보를 순서대로 시도해 첫 매칭 셀렉터를 반환한다.

    exists_fn(selector) -> bool 은 실제로는 querySelector 존재 여부에
    해당한다. 여기서는 가짜 페이지 dict로 대체해 로직만 검증한다.
    """
    for selector in selectors:
        if exists_fn(selector):
            return selector
    return None


def main() -> None:
    # 가짜 페이지: 어떤 셀렉터가 실제 DOM에 존재하는지 흉내
    fake_page = {".btn-primary", "button[type=submit]"}

    candidates = ["#submit-btn", ".btn-primary", "button[type=submit]"]
    found = try_selectors(candidates, lambda sel: sel in fake_page)

    print(f"셀렉터 후보: {candidates}")
    print(f"가짜 페이지에 존재하는 셀렉터: {fake_page}")
    print(f"선택된 셀렉터: {found}")
    assert found == ".btn-primary"
    print("\n검증 통과: 첫 번째 미매칭 후보를 건너뛰고 두 번째에서 채택")


if __name__ == "__main__":
    main()
