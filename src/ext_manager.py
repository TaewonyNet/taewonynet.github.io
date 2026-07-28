"""
크롬 확장 버전을 읽어 알려진 선택자 집합과 대조한다.

확장 팝업 UI는 버전마다 선택자가 바뀐다. 이 모듈은:
  1. manifest.json에서 현재 버전을 읽는다.
  2. major 버전별 선택자 테이블에서 해당 버전의 선택자를 꺼낸다.
  3. 모르는 버전이면 즉시 RuntimeError — 조용한 실패 대신 즉시 표면화.
  4. 선택적으로 팝업을 열어 핵심 선택자가 실제로 존재하는지 확인한다.

대상: 'Free VPN for Chrome - VPN Proxy'(majdfhpaihoncoakbjgbdhglocklcgno)
requirements: playwright (검증 실행 시), pyvirtualdisplay
"""

import json
import pathlib
import time
from typing import Optional

EXT_DIR = pathlib.Path(__file__).parent / "extensions" / "majdfhpaihoncoakbjgbdhglocklcgno" / "unpacked"

# ─────────────────────────────────────────────
# 버전별 선택자 테이블
# 새 버전이 나오면 여기에 추가하고 기존 항목은 유지한다.
# ─────────────────────────────────────────────

_SELECTOR_TABLE: dict[str, dict] = {
    "4": {
        # 온보딩 — 순서대로 클릭해야 메인 화면 도달
        "onboarding": [
            ".free-step__btn",
            ".premium-step__btn",
            ".pricing-step__action--free",
            ".trial-modal__close",
        ],
        # 메인 화면
        "splash":       ".splash-screen",
        "region_btn":   ".connect-region__location",
        "connect_btn":  ".connect-button",
        # 지역 목록
        "search":       ".search-input__input",
        "simple_loc":   ".simple-location",
        "simple_name":  ".simple-location__country-name",
        "simple_crown": ".simple-location__crown",
        "multi_loc":    ".multi-region-location__country",
        "multi_name":   ".multi-region-location__country-name",
        "multi_crown":  ".multi-region-location__crown",
        "multi_region": ".multi-region-location__region",
    },
    "3": {
        "onboarding": [".intro-steps__btn"],
        "splash":       None,
        "region_btn":   ".connect-region__location",
        "connect_btn":  ".connect-button",
        "search":       None,
        "simple_loc":   ".location-country",
        "simple_name":  ".location-country__header",
        "simple_crown": ".location-country--blocked",
        "multi_loc":    None,
        "multi_name":   None,
        "multi_crown":  None,
        "multi_region": None,
    },
}

# 버전 업데이트 시 UI 검증에 쓸 필수 선택자 (없으면 즉시 에러)
_REQUIRED_KEYS = ["region_btn", "connect_btn"]


# ─────────────────────────────────────────────
# 버전 읽기 + 선택자 반환
# ─────────────────────────────────────────────

def get_version(ext_dir: pathlib.Path = EXT_DIR) -> str:
    """manifest.json에서 현재 확장 버전을 반환한다."""
    mf = ext_dir / "manifest.json"
    if not mf.exists():
        raise FileNotFoundError(f"manifest.json 없음: {mf}")
    data = json.loads(mf.read_text())
    version = data.get("version", "")
    if not version:
        raise RuntimeError("manifest.json에 version 필드가 없음")
    return version


def get_selectors(version: Optional[str] = None,
                  ext_dir: pathlib.Path = EXT_DIR) -> dict:
    """
    버전에 맞는 선택자 딕셔너리를 반환한다.
    version이 None이면 manifest.json에서 자동으로 읽는다.
    알려지지 않은 major 버전이면 즉시 RuntimeError.
    """
    if version is None:
        version = get_version(ext_dir)
    major = version.split(".")[0]
    if major not in _SELECTOR_TABLE:
        known = list(_SELECTOR_TABLE.keys())
        raise RuntimeError(
            f"확장 버전 {version}(major={major})의 선택자 정의가 없다. "
            f"알려진 버전: {known}. ext_manager.py의 _SELECTOR_TABLE에 추가 필요."
        )
    return _SELECTOR_TABLE[major]


# ─────────────────────────────────────────────
# 팝업 UI 검증 (Playwright)
# ─────────────────────────────────────────────

def verify_ui(ext_id: str, selectors: dict, profile_dir: pathlib.Path) -> None:
    """
    Playwright로 팝업을 열어 핵심 선택자가 실제로 존재하는지 확인한다.
    선택자가 없으면 즉시 RuntimeError — 조용한 실패를 에러로 드러낸다.
    """
    import glob, os
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    # 최신 Playwright Chromium 선택 (버전 오름차순 마지막)
    candidates = sorted(
        glob.glob(str(pathlib.Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux64/chrome")),
        reverse=True,
    )
    chromium = os.environ.get("PLAYWRIGHT_CHROMIUM") or (candidates[0] if candidates else None)

    ext_dir_abs = str(EXT_DIR.absolute())
    display = None
    try:
        from pyvirtualdisplay import Display
        display = Display(visible=0, size=(1280, 800))
        display.start()
    except ImportError:
        pass

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                executable_path=chromium,
                ignore_default_args=["--disable-extensions"],
                args=[
                    f"--load-extension={ext_dir_abs}",
                    f"--disable-extensions-except={ext_dir_abs}",
                    "--no-sandbox", "--disable-dev-shm-usage",
                ],
            )
            page = ctx.new_page()
            page.goto(f"chrome-extension://{ext_id}/src/popup/popup.html")

            # 스플래시 대기
            if selectors.get("splash"):
                try:
                    page.wait_for_selector(selectors["splash"], state="hidden", timeout=15000)
                except PWTimeout:
                    pass
            time.sleep(0.5)

            # 온보딩 건너뛰기
            for sel in selectors.get("onboarding", []):
                try:
                    el = page.locator(sel).first
                    el.wait_for(state="visible", timeout=5000)
                    el.click()
                    time.sleep(1.2)
                except PWTimeout:
                    pass

            # 핵심 선택자 존재 확인
            missing = []
            for key in _REQUIRED_KEYS:
                sel = selectors.get(key)
                if sel and not page.locator(sel).count():
                    missing.append(f"{key}={sel!r}")

            ctx.close()

            if missing:
                raise RuntimeError(
                    f"팝업에서 선택자 누락 — 확장 UI가 바뀌었을 수 있음: {missing}\n"
                    "ext_manager.py의 _SELECTOR_TABLE을 업데이트하세요."
                )
            print("UI 검증 통과: 모든 필수 선택자 확인됨")
    finally:
        if display:
            display.stop()


# ─────────────────────────────────────────────
# 독립 실행 — 버전 확인 + 선택자 목록 출력
# ─────────────────────────────────────────────

def main(ext_dir: pathlib.Path = EXT_DIR, verify: bool = False) -> None:
    if not (ext_dir / "manifest.json").exists():
        print("확장이 없습니다. chrome_ext_downloader.py의 download()를 먼저 실행하세요.")
        return

    version = get_version(ext_dir)
    print(f"확장 버전: {version}")

    selectors = get_selectors(version)  # 모르는 버전이면 여기서 에러
    print(f"선택자 테이블(major={version.split('.')[0]}):")
    for key, val in selectors.items():
        print(f"  {key}: {val}")

    if verify:
        # chrome://extensions-internals로 ext_id 자동 감지
        import glob, os
        from playwright.sync_api import sync_playwright
        candidates = sorted(
            glob.glob(str(pathlib.Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux64/chrome")),
            reverse=True,
        )
        chromium = os.environ.get("PLAYWRIGHT_CHROMIUM") or (candidates[0] if candidates else None)
        profile = ext_dir.parent.parent / "vpn_chrome_profile_cdp"
        profile.mkdir(parents=True, exist_ok=True)

        display = None
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=0, size=(1280, 800))
            display.start()
        except ImportError:
            pass

        try:
            with sync_playwright() as p:
                ctx = p.chromium.launch_persistent_context(
                    user_data_dir=str(profile),
                    headless=False,
                    executable_path=chromium,
                    ignore_default_args=["--disable-extensions"],
                    args=[
                        f"--load-extension={ext_dir.absolute()}",
                        f"--disable-extensions-except={ext_dir.absolute()}",
                        "--no-sandbox", "--disable-dev-shm-usage",
                    ],
                )
                page = ctx.new_page()
                page.goto("chrome://extensions-internals")
                time.sleep(2)
                raw = page.locator("pre").text_content(timeout=5000) or "[]"
                ext_ids = [e["id"] for e in json.loads(raw) if e.get("location") != "COMPONENT" and e.get("id")]
                ctx.close()

            if not ext_ids:
                raise RuntimeError("로드된 확장 ID를 찾지 못함")

            ext_id = ext_ids[0]
            print(f"확장 ID: {ext_id}")
            verify_ui(ext_id, selectors, profile)
        finally:
            if display:
                display.stop()


if __name__ == "__main__":
    import sys
    verify_flag = "--verify" in sys.argv
    main(verify=verify_flag)
