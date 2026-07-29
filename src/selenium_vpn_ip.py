"""
셀레니움 + --load-extension으로 VPN 크롬 확장을 올려 우회 IP를 확인한다.

배경:
  Google Chrome 130 미만(또는 Chromium 기반 빌드)에서는 --load-extension이 동작한다.
  Chrome 130부터 바이너리 수준에서 차단됐다. 이 스크립트는 Chrome 130 이전 환경 또는
  Chromium에서 동작한다고 가정한다. 현재 환경이 Google Chrome 130+ 라면
  playwright_vpn_ip.py(Playwright Chromium 방식)를 사용하라.

흐름:
  [최초 1회] download() → chrome_ext_downloader로 확장 CRX 다운로드 + 압축 해제
  [매 실행]  main()     → --load-extension → 팝업 조작 → IP 비교

주의:
  chromedriver는 Chrome 버전과 반드시 일치해야 한다.
  Chrome 130 이전 버전 + 그 버전용 chromedriver를 사용하거나,
  executable_path 인수로 번들 chromedriver 경로를 직접 지정한다.

선택자 기준: 'Free VPN for Chrome - VPN Proxy'(majdfh...) v4.x
requirements: selenium, webdriver-manager, pyvirtualdisplay, chrome_ext_downloader
"""

import json
import pathlib
import time
from typing import Optional

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

VPN_STORE_ID = "majdfhpaihoncoakbjgbdhglocklcgno"
IP_ECHO = "https://api.ip.pe.kr"
EXT_DIR = pathlib.Path(__file__).parent / "extensions" / VPN_STORE_ID / "unpacked"

# v4.x 온보딩 — 순서대로 클릭해야 메인 화면에 도달
_ONBOARD_SELECTORS = [
    ".free-step__btn",            # 1단계: "Continue"
    ".premium-step__btn",         # 2단계: "Start" (프리미엄 피치)
    ".pricing-step__action--free", # 3단계: "Continue with Free"
    ".trial-modal__close",        # 4단계: 트라이얼 모달 닫기 (X 버튼)
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

    # --load-extension용: Chromium이 원격 업데이트를 거부하지 않도록 update_url 제거
    mf = unpacked / "manifest.json"
    data = json.loads(mf.read_text())
    data.pop("update_url", None)
    mf.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    print(f"다운로드 완료: {unpacked}")
    return unpacked


# ─────────────────────────────────────────────
# 드라이버 생성
# ─────────────────────────────────────────────

def _make_driver(ext_dir: pathlib.Path,
                 chromedriver_path: Optional[str] = None) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()

    # --load-extension: Chrome 130 미만 / Chromium에서만 동작
    options.add_argument(f"--load-extension={ext_dir.absolute()}")

    # 구버전 자동화 환경에서 흔히 쓰이던 안정화 플래그
    options.add_argument("--disable-extensions-file-access-check")
    options.add_argument("--disable-extensions-http-throttling")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_experimental_option("prefs", {"extensions.ui.developer_mode": True})

    if chromedriver_path:
        service = Service(executable_path=chromedriver_path)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())

    return webdriver.Chrome(service=service, options=options)


# ─────────────────────────────────────────────
# 공용 헬퍼
# ─────────────────────────────────────────────

def _wait_el(driver: webdriver.Chrome, selector: str,
             timeout: int = 5) -> Optional[object]:
    try:
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
    except TimeoutException:
        return None


def _resolve_ext_id(driver: webdriver.Chrome) -> str:
    """chrome://extensions 의 shadow DOM에서 로드된 확장 ID를 찾는다."""
    driver.get("chrome://extensions")
    time.sleep(2)
    items = driver.execute_script("""
      const m = document.querySelector('extensions-manager');
      if (!m) return [];
      const list = m.shadowRoot.querySelector('extensions-item-list');
      if (!list) return [];
      return [...list.shadowRoot.querySelectorAll('extensions-item')].map(it => ({
        id: it.id,
        name: it.shadowRoot.querySelector('#name')?.textContent.trim()
      }));
    """) or []
    for it in items:
        if it.get("name") and "vpn" in it["name"].lower():
            return it["id"]
    raise RuntimeError(f"로드된 확장에서 VPN을 찾지 못함 (--load-extension이 차단됐거나 크롬 버전 불일치): {items}")


def _current_ip(driver: webdriver.Chrome) -> str:
    driver.get(IP_ECHO)
    WebDriverWait(driver, 15).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    return driver.find_element(By.TAG_NAME, "body").text.strip()


def _skip_onboarding(driver: webdriver.Chrome) -> None:
    """v4.x 온보딩 4단계를 순서대로 건너뛴다."""
    for sel in _ONBOARD_SELECTORS:
        el = _wait_el(driver, sel, timeout=5)
        if el:
            el.click()
            time.sleep(1.2)


# ─────────────────────────────────────────────
# VPN 연결
# ─────────────────────────────────────────────

def connect_vpn(driver: webdriver.Chrome, ext_id: str,
                country: str = "United Kingdom") -> None:
    """
    확장 팝업을 열어 온보딩을 건너뛰고 국가를 선택해 연결한다.

    v4.x 선택자:
      온보딩: .free-step__btn / .premium-step__btn / .pricing-step__action--free / .trial-modal__close
      검색: .search-input__input
      단일 지역: .simple-location / .simple-location__country-name / .simple-location__crown
      복수 지역: .multi-region-location__country / .multi-region-location__country-name
      연결: .connect-button
    """
    driver.get(f"chrome-extension://{ext_id}/src/popup/popup.html")

    # 스플래시 화면 사라질 때까지 대기
    try:
        WebDriverWait(driver, 15).until(
            EC.invisibility_of_element_located((By.CSS_SELECTOR, ".splash-screen"))
        )
    except TimeoutException:
        pass
    time.sleep(0.5)

    _skip_onboarding(driver)

    # 메인 화면 대기
    _wait_el(driver, ".connect-region__location", timeout=10)

    # 지역 목록 열기
    driver.find_element(By.CSS_SELECTOR, ".connect-region__location").click()
    time.sleep(2)

    # 검색 필터링
    search = _wait_el(driver, ".search-input__input", timeout=5)
    if search:
        search.clear()
        search.send_keys(country)
        time.sleep(1.5)

    found = False
    country_lower = country.lower()

    # ① multi-region (United Kingdom처럼 하위 지역이 있는 국가)
    for loc in driver.find_elements(By.CSS_SELECTOR, ".multi-region-location__country"):
        if loc.find_elements(By.CSS_SELECTOR, ".multi-region-location__crown"):
            continue
        names = loc.find_elements(By.CSS_SELECTOR, ".multi-region-location__country-name")
        if not names:
            continue
        nm = names[0].text.strip().lower()
        if country_lower in nm or nm in country_lower:
            loc.click()
            time.sleep(1.5)
            for r in driver.find_elements(By.CSS_SELECTOR, ".multi-region-location__region"):
                cls = r.get_attribute("class") or ""
                if "active" not in cls:
                    r.click()
                    found = True
                    break
            if not found:
                regs = driver.find_elements(By.CSS_SELECTOR, ".multi-region-location__region")
                if regs:
                    regs[0].click()
                    found = True
            break

    if not found:
        # ② simple-location (단일 지역 국가)
        for loc in driver.find_elements(By.CSS_SELECTOR, ".simple-location"):
            if loc.find_elements(By.CSS_SELECTOR, ".simple-location__crown"):
                continue
            names = loc.find_elements(By.CSS_SELECTOR, ".simple-location__country-name")
            if not names:
                continue
            nm = names[0].text.strip().lower()
            if country_lower in nm or nm in country_lower:
                loc.click()
                found = True
                break

    if not found:
        # ③ 폴백: 첫 번째 무료 simple-location
        for loc in driver.find_elements(By.CSS_SELECTOR, ".simple-location"):
            if not loc.find_elements(By.CSS_SELECTOR, ".simple-location__crown"):
                nm = loc.find_elements(By.CSS_SELECTOR, ".simple-location__country-name")
                print(f"폴백: {nm[0].text.strip() if nm else ''}")
                loc.click()
                found = True
                break

    if not found:
        raise RuntimeError(f"'{country}' 무료 위치를 찾지 못함")

    time.sleep(2)

    connect_btn = _wait_el(driver, ".connect-button", timeout=10)
    if not connect_btn:
        raise RuntimeError(".connect-button 없음")
    connect_btn.click()
    time.sleep(5)  # VPN 핸드셰이크 대기


# ─────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────

def main(country: str = "United Kingdom",
         chromedriver_path: Optional[str] = None,
         ext_dir: pathlib.Path = EXT_DIR) -> None:
    """
    Selenium으로 VPN 확장을 로드하고 국가를 선택해 IP 변화를 확인한다.
    Chrome 130 이전 또는 Chromium + 맞는 chromedriver가 필요하다.
    """
    if not (ext_dir / "manifest.json").exists():
        print("확장이 없습니다. download()를 먼저 실행하세요.")
        return

    display = None
    try:
        from pyvirtualdisplay import Display
        display = Display(visible=0, size=(1280, 800))
        display.start()
    except ImportError:
        pass

    driver = _make_driver(ext_dir, chromedriver_path)
    try:
        ext_id = _resolve_ext_id(driver)
        print(f"확장 ID: {ext_id}")

        before = _current_ip(driver)
        print(f"연결 전 IP: {before}")

        connect_vpn(driver, ext_id, country)

        after = _current_ip(driver)
        print(f"연결 후 IP: {after}")
        print("우회 성공!" if before != after else "IP 변화 없음")
    finally:
        driver.quit()
        if display:
            display.stop()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "download":
        download()
    else:
        country = sys.argv[1] if len(sys.argv) > 1 else "United Kingdom"
        main(country=country)
