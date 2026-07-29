"""
Playwright Chromium으로 VPN 크롬 확장을 올려 우회 IP를 확인한다.

배경:
  Google Chrome 130+는 --load-extension을 바이너리 수준에서 차단한다.
  Playwright가 번들로 가져오는 Chromium(Google Chrome이 아님)은 차단하지 않으므로
  --load-extension + 압축 해제 폴더로 확장을 자동 로드할 수 있다.

흐름:
  [최초 1회] download() → chrome_ext_downloader로 확장 CRX 다운로드 + 압축 해제
  [매 실행]  main()     → Playwright Chromium + --load-extension → 팝업 조작 → IP 비교

선택자 기준: 'Free VPN for Chrome - VPN Proxy'(majdfh...) v4.x
requirements: playwright, pyvirtualdisplay, chrome_ext_downloader
"""

import json
import pathlib
import time
from typing import Optional

from playwright.sync_api import Page, sync_playwright, TimeoutError as PWTimeout

VPN_STORE_ID = "majdfhpaihoncoakbjgbdhglocklcgno"
IP_ECHO = "https://api.ip.pe.kr"
EXT_DIR = pathlib.Path(__file__).parent / "extensions" / VPN_STORE_ID / "unpacked"
_PW_PROFILE = pathlib.Path(__file__).parent / "vpn_chrome_profile_cdp"

# Playwright 번들 Chromium — 1208(145)은 SIGTRAP, 1217(147)이 안정적
# 환경 변수나 더 새 버전이 있으면 그쪽을 우선 쓴다
def _find_chromium() -> Optional[str]:
    import glob, os
    if path := os.environ.get("PLAYWRIGHT_CHROMIUM"):
        return path
    candidates = sorted(
        glob.glob(str(pathlib.Path.home() / ".cache/ms-playwright/chromium-*/chrome-linux64/chrome")),
        reverse=True,
    )
    return candidates[0] if candidates else None

# ─────────────────────────────────────────────
# v4.x 온보딩 선택자 (순서대로 클릭)
# ─────────────────────────────────────────────
_ONBOARD_SELECTORS = [
    ".free-step__btn",          # 1단계: "Continue"
    ".premium-step__btn",       # 2단계: "Start" (프리미엄 피치)
    ".pricing-step__action--free",  # 3단계: "Continue with Free"
    ".trial-modal__close",      # 4단계: 트라이얼 모달 닫기 (X 버튼)
]


# ─────────────────────────────────────────────
# 최초 1회: 확장 다운로드
# ─────────────────────────────────────────────

def download(ext_id: str = VPN_STORE_ID) -> pathlib.Path:
    """웹 스토어에서 CRX를 받아 압축 해제한다. 이미 있으면 건너뛴다."""
    if EXT_DIR.exists() and (EXT_DIR / "manifest.json").exists():
        print(f"이미 존재: {EXT_DIR}")
        return EXT_DIR

    import chrome_ext_downloader
    store_url = f"https://chromewebstore.google.com/detail/{ext_id}"
    unpacked = pathlib.Path(chrome_ext_downloader.process(store_url))

    # Chromium이 사설 확장으로 거부하지 않도록 update_url 제거
    mf = unpacked / "manifest.json"
    data = json.loads(mf.read_text())
    data.pop("update_url", None)
    mf.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    print(f"다운로드 완료: {unpacked}")
    return unpacked


# ─────────────────────────────────────────────
# 공용 헬퍼
# ─────────────────────────────────────────────

def _click_if_visible(page: Page, selector: str, timeout: int = 5000) -> bool:
    try:
        el = page.locator(selector).first
        el.wait_for(state="visible", timeout=timeout)
        el.click()
        time.sleep(1.2)
        return True
    except PWTimeout:
        return False


def _skip_onboarding(page: Page) -> None:
    """v4.x 온보딩 4단계를 순서대로 건너뛴다."""
    for sel in _ONBOARD_SELECTORS:
        _click_if_visible(page, sel, timeout=5000)


def _current_ip(page: Page) -> str:
    page.goto(IP_ECHO)
    page.wait_for_load_state("networkidle", timeout=15000)
    raw = page.locator("body").text_content() or ""
    return raw.split("@")[0].strip()


def _resolve_ext_id(page: Page) -> str:
    """chrome://extensions-internals 에서 로드된 확장 ID를 찾는다."""
    page.goto("chrome://extensions-internals")
    time.sleep(2)
    raw = page.locator("pre").text_content(timeout=5000) or "[]"
    for e in json.loads(raw):
        if e.get("location") != "COMPONENT" and e.get("id"):
            return e["id"]
    raise RuntimeError("로드된 비컴포넌트 확장을 찾지 못함")


# ─────────────────────────────────────────────
# VPN 연결
# ─────────────────────────────────────────────

def connect_vpn(page: Page, ext_id: str, country: str = "United Kingdom") -> None:
    """
    확장 팝업을 열어 온보딩을 건너뛰고 국가를 선택해 연결한다.

    v4.x 선택자:
      온보딩: .free-step__btn / .premium-step__btn / .pricing-step__action--free / .trial-modal__close
      검색: .search-input__input
      단일 지역: .simple-location / .simple-location__country-name / .simple-location__crown
      복수 지역: .multi-region-location__country / .multi-region-location__country-name / .multi-region-location__crown
      연결: .connect-button
    """
    page.goto(f"chrome-extension://{ext_id}/src/popup/popup.html")

    # 스플래시 화면이 사라질 때까지 대기
    try:
        page.wait_for_selector(".splash-screen", state="hidden", timeout=15000)
    except PWTimeout:
        pass
    time.sleep(0.5)

    _skip_onboarding(page)

    # 메인 화면 대기
    page.wait_for_selector(".connect-region__location", timeout=10000, state="visible")

    # 지역 목록 열기
    page.locator(".connect-region__location").first.click()
    time.sleep(2)

    # 검색 필터링
    try:
        page.wait_for_selector(".search-input__input", timeout=5000, state="visible")
        page.locator(".search-input__input").fill(country)
        time.sleep(1.5)
    except PWTimeout:
        pass

    found = False
    country_lower = country.lower()

    # ① multi-region (United Kingdom처럼 하위 지역이 있는 국가)
    for loc in page.locator(".multi-region-location__country").all():
        try:
            if loc.locator(".multi-region-location__crown").count():
                continue  # 프리미엄 전용
            name_el = loc.locator(".multi-region-location__country-name")
            if not name_el.count():
                continue
            nm = name_el.text_content().strip().lower()
            if country_lower in nm or nm in country_lower:
                loc.click()
                time.sleep(1.5)
                regions = page.locator(".multi-region-location__region").all()
                for r in regions:
                    cls = r.get_attribute("class") or ""
                    if "active" not in cls:
                        r.click()
                        found = True
                        break
                if not found and regions:
                    regions[0].click()
                    found = True
                break
        except Exception:
            continue

    if not found:
        # ② simple-location (단일 지역 국가)
        for loc in page.locator(".simple-location").all():
            try:
                if loc.locator(".simple-location__crown").count():
                    continue
                name_el = loc.locator(".simple-location__country-name")
                if not name_el.count():
                    continue
                nm = name_el.text_content().strip().lower()
                if country_lower in nm or nm in country_lower:
                    loc.click()
                    found = True
                    break
            except Exception:
                continue

    if not found:
        # ③ 폴백: 첫 번째 무료 simple-location
        for loc in page.locator(".simple-location").all():
            try:
                if not loc.locator(".simple-location__crown").count():
                    nm = (loc.locator(".simple-location__country-name").first.text_content() or "").strip()
                    print(f"폴백 선택: {nm}")
                    loc.click()
                    found = True
                    break
            except Exception:
                continue

    if not found:
        raise RuntimeError(f"'{country}' 무료 위치를 찾지 못함 (프리미엄만 있거나 목록 비어있음)")

    time.sleep(2)

    # 연결 버튼 클릭 (연결 완료 선택자는 버전마다 다르므로 시간으로 대기)
    page.wait_for_selector(".connect-button", timeout=10000, state="visible")
    page.locator(".connect-button").first.click()
    time.sleep(5)  # VPN 핸드셰이크 대기


# ─────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────

def main(country: str = "United Kingdom", headless: bool = False,
         ext_dir: pathlib.Path = EXT_DIR,
         profile_dir: pathlib.Path = _PW_PROFILE) -> None:
    """
    Playwright Chromium으로 VPN 확장을 로드하고 국가를 선택해 IP 변화를 확인한다.
    최초 실행 전에 download()로 확장을 받아야 한다.
    """
    if not (ext_dir / "manifest.json").exists():
        print("확장이 없습니다. download()를 먼저 실행하세요.")
        return

    display = None
    if not headless:
        try:
            from pyvirtualdisplay import Display
            display = Display(visible=0, size=(1280, 800))
            display.start()
        except ImportError:
            pass

    profile_dir.mkdir(parents=True, exist_ok=True)

    try:
        with sync_playwright() as p:
            chromium_path = _find_chromium()
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                executable_path=chromium_path,
                ignore_default_args=["--disable-extensions"],
                args=[
                    f"--load-extension={ext_dir.absolute()}",
                    f"--disable-extensions-except={ext_dir.absolute()}",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            page = ctx.new_page()

            ext_id = _resolve_ext_id(page)
            print(f"확장 ID: {ext_id}")

            before = _current_ip(page)
            print(f"연결 전 IP: {before}")

            connect_vpn(page, ext_id, country)

            after = _current_ip(page)
            print(f"연결 후 IP: {after}")
            print("우회 성공!" if before != after else "IP 변화 없음")

            ctx.close()
    finally:
        if display:
            display.stop()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "download":
        download()
    else:
        country = sys.argv[1] if len(sys.argv) > 1 else "United Kingdom"
        main(country=country)
