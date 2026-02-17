import asyncio
import logging
import random
import sys
from typing import Dict, Optional, List, Any

import httpx
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from pyvirtualdisplay import Display  # 가상 화면용

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WebMetaApp")

from dependency import dependency_check

dependency_check({
    "flask": "flask",
    "playwright": "playwright",
    "bs4": "beautifulsoup4",
    "httpx": "httpx",
    "pyvirtualdisplay": "pyvirtualdisplay"
})

DEFAULT_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]


class WebClient:
    def __init__(self, user_agents: Optional[List[str]] = None, timeout: int = 10000):
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.timeout = timeout
        self.display = None
        self.pw = None
        self.browser = None
        self.http_client = httpx.AsyncClient(
            headers={"User-Agent": random.choice(self.user_agents)},
            timeout=self.timeout / 1000
        )

    async def _start_virtual_display(self):
        """가상 화면을 시작합니다."""
        try:
            self.display = Display(visible=0, size=(1280, 720))
            self.display.start()
            logger.info("가상 화면(Virtual Display) 시작됨")
        except Exception as e:
            logger.warning(f"가상 화면 시작 실패 (OS 환경 확인 필요): {e}")

    async def login_and_dump_cookies(self, url: str, username: str, password: str):
        """Playwright(Headless=False)로 로그인 후 쿠키를 추출합니다."""
        await self._start_virtual_display()

        self.pw = await async_playwright().start()
        # 가상 화면 안에서 Headless=False로 실행
        self.browser = await self.pw.chromium.launch(headless=False)
        context = await self.browser.new_context()
        page = await context.new_page()

        try:
            logger.info(f"브라우저 로그인 시도: {url}")
            await page.goto(url)
            await page.fill('input[name="id"]', username)
            await page.fill('input[name="pw"]', password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")

            # 쿠키 추출 및 httpx 주입
            cookies = await context.cookies()
            for cookie in cookies:
                self.http_client.cookies.set(
                    cookie['name'],
                    cookie['value'],
                    domain=cookie['domain']
                )
            logger.info(f"성공적으로 {len(cookies)}개의 쿠키를 덤프하여 httpx에 주입했습니다.")

        finally:
            await self.browser.close()
            await self.pw.stop()
            if self.display:
                self.display.stop()

    async def extract_meta(self, url: str, max_retries: int = 2) -> Dict[str, Any]:
        """주입된 쿠키를 가진 httpx를 사용하여 빠르게 데이터를 추출합니다."""
        for attempt in range(max_retries + 1):
            try:
                resp = await self.http_client.get(url)
                resp.raise_for_status()
                return self._parse_html(resp.text)
            except Exception as e:
                if attempt == max_retries:
                    return {"error": str(e)}
                await asyncio.sleep(0.5)
        return {}

    def _parse_html(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, 'html.parser')
        meta = {}
        if title := soup.find('title'):
            meta['title'] = title.get_text(strip=True)
        # (기존 og 태그 추출 로직 동일...)
        for prop in ['og:title', 'og:description', 'og:image', 'og:url']:
            tag = soup.find('meta', attrs={'property': prop}) or soup.find('meta', attrs={'name': prop})
            if tag:
                meta[prop.replace('og:', 'og_')] = tag.attrs.get('content', '').strip()
        return meta

    async def close(self):
        await self.http_client.aclose()


async def run_test():
    import demoserver
    url = "http://127.0.0.1:5000"
    demoserver.run(is_while=False)

    client = WebClient()

    try:
        logger.info("--- Phase 1: Guest (Async) ---")
        meta_user = await client.extract_meta(url)
        for k, v in meta_user.items():
            logger.info(f"[{k:<12}] {v}")

        # 1단계: Playwright + 가상화면으로 로그인 후 쿠키 탈취
        await client.login_and_dump_cookies(url, "tester", "password")

        # 2단계: httpx로 실제 데이터 추출 (매우 빠름)
        logger.info("--- Phase 2: User (Async) ---")
        meta_user = await client.extract_meta(url)
        for k, v in meta_user.items():
            logger.info(f"[{k:<12}] {v}")
    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        logger.info("Stopped.")
