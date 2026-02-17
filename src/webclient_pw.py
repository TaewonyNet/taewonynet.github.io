import asyncio
import logging
import random
import sys
from typing import Dict, Optional, List, Any

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
})

DEFAULT_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

class WebClient:
    def __init__(self, user_agents: Optional[List[str]] = None, timeout: int = 10000):
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.timeout = timeout
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None

    async def init_browser(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context(
            user_agent=random.choice(self.user_agents)
        )
        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.timeout)

    async def login(self, url: str, username: str, password: str):
        await self.page.goto(url)
        await self.page.fill('input[name="id"]', username)
        await self.page.fill('input[name="pw"]', password)
        await self.page.click('button[type="submit"]')
        await self.page.wait_for_load_state("networkidle")

    async def extract_meta(self, url: str, max_retries: int = 2) -> Dict[str, Any]:
        for attempt in range(max_retries + 1):
            try:
                await self.page.goto(url)
                await self.page.wait_for_load_state("domcontentloaded")
                content = await self.page.content()
                return self._parse_html(content)
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

        if desc := soup.find('meta', attrs={'name': 'description'}):
            meta['description'] = desc.attrs.get('content', '').strip()

        for prop in ['og:title', 'og:description', 'og:image', 'og:url']:
            tag = soup.find('meta', attrs={'property': prop}) or soup.find('meta', attrs={'name': prop})
            if tag:
                meta[prop.replace('og:', 'og_')] = tag.attrs.get('content', '').strip()
        return meta

    async def close(self):
        """브라우저 자원을 해제합니다."""
        if self.browser:
            await self.browser.close()
        if self.pw:
            await self.pw.stop()


async def run_test():
    import demoserver
    url = "http://127.0.0.1:5000"
    demoserver.run(is_while=False)

    client = WebClient()
    await client.init_browser()

    try:
        logger.info("--- Phase 1: Guest (Playwright) ---")
        meta_guest = await client.extract_meta(url)
        for k, v in meta_guest.items():
            logger.info(f"[{k:<12}] {v}")

        logger.info("--- Phase 2: User (Playwright) ---")
        await client.login(url, "tester", "password")
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