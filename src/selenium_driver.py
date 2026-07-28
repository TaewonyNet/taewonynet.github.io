"""
셀레니움 드라이버 클래스 래퍼 — 매번 반복되는 세팅을 한 곳에 모은다.

webdriver.Chrome 을 상속해 ① 봇탐지 우회 옵션 ② 확장 로드 ③ 프록시
④ 도메인별 쿠키 영속 ⑤ 안정적 대기 헬퍼 ⑥ alert 억제 ⑦ 스크린샷을
기본 제공한다. 사이트별 스크립트는 이 위에서 얇게 작성한다.

requirements: selenium, webdriver-manager
"""

import logging
import os
import pickle
from urllib.parse import urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("SeleniumDriver")


class Driver(webdriver.Chrome):
    """반복 세팅을 흡수한 Chrome 드라이버 래퍼."""

    def __init__(self, headless=True, extensions=None, proxy=None,
                 resolution="1920x1080", lang="ko-KR",
                 cookie_path="cookies.pkl", executable_path="chromedriver",
                 user_data_dir=None):
        options = webdriver.ChromeOptions()

        # ① 봇탐지 우회 — 자동화 흔적 제거
        options.add_experimental_option("excludeSwitches",
                                        ["enable-logging", "enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-blink-features=AutomationControlled")

        # ② 확장 로드 (여러 개 가능) — Chromium에서만 동작; Google Chrome 130+는 차단
        if extensions:
            if not isinstance(extensions, list):
                extensions = [extensions]
            paths = ",".join(os.path.abspath(x) for x in extensions)
            options.add_argument(f"--load-extension={paths}")

        # ③ 영구 프로필 (미리 확장이 설치된 디렉터리를 재사용할 때)
        if user_data_dir:
            options.add_argument(f"--user-data-dir={os.path.abspath(user_data_dir)}")

        # ④ 프록시
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")

        # 공통 안정화 옵션
        options.add_argument(f"--window-size={resolution}")
        options.add_argument(f"--lang={lang}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        if headless:
            options.add_argument("--headless=new")

        try:
            super().__init__(service=Service(executable_path), options=options)
        except Exception:
            from webdriver_manager.chrome import ChromeDriverManager
            super().__init__(service=Service(ChromeDriverManager().install()), options=options)

        # ④ 도메인별 쿠키 영속
        self.cookie_path = cookie_path
        self.cookies = pickle.load(open(cookie_path, "rb")) if os.path.exists(cookie_path) else {}

    # ⑤ 안정적 대기 — 매번 WebDriverWait 짜지 않는다
    def wait_for_load(self, timeout=20):
        try:
            WebDriverWait(self, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete")
        except TimeoutException:
            logger.warning("페이지 로드 타임아웃")
        return self

    def wait_el(self, selector, timeout=5, by=By.CSS_SELECTOR, clickable=True):
        action = EC.element_to_be_clickable if clickable else EC.presence_of_element_located
        try:
            return WebDriverWait(self, timeout).until(action((by, selector)))
        except TimeoutException:
            logger.warning(f"요소 대기 실패: {selector}")
            return None

    # ⑥ alert/confirm 억제 — 자동화 흐름이 모달에 막히지 않게
    def suppress_dialogs(self):
        self.execute_script("window.alert=function(){};window.confirm=function(){return true;};")
        return self

    # 도메인별 쿠키 저장/복원 — 재로그인 회피
    def _domain(self, url=None):
        return urlparse(url or self.current_url).netloc

    def save_cookie(self):
        self.cookies[self._domain()] = self.get_cookies()
        pickle.dump(self.cookies, open(self.cookie_path, "wb"))

    def load_cookie(self):
        for c in self.cookies.get(self._domain(), []):
            try:
                self.add_cookie(c)
            except Exception:
                pass
        return self

    # ⑦ 스크린샷
    def shot(self, filename="shot.png"):
        self.save_screenshot(filename)
        return filename


if __name__ == "__main__":
    # 공개 사이트로 데모 — 래퍼 한 줄로 세팅 끝
    d = Driver(headless=True)
    try:
        d.get("https://example.com")
        d.wait_for_load().suppress_dialogs()
        el = d.wait_el("h1")
        print("제목:", el.text if el else "(없음)")
        d.save_cookie()
        print("쿠키 도메인:", list(d.cookies))
        print("스크린샷:", d.shot())
    finally:
        d.quit()
