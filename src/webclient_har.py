import re
import asyncio
import logging
import random
import sys
import json
import os
from typing import Dict, Optional, List, Any

import httpx
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from pyvirtualdisplay import Display

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
        self.har_path = "session_record.har"  # HAR 파일 저장 경로
        self._entries = {}

        self.http_client = httpx.AsyncClient(
            headers={"User-Agent": random.choice(self.user_agents)},
            timeout=self.timeout / 1000,
            follow_redirects=True
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
        """Playwright로 로그인하며 HAR 로그를 기록하고 쿠키를 추출합니다."""
        await self._start_virtual_display()

        self.pw = await async_playwright().start()
        # 가상 화면 안에서 Headless=False로 실행
        self.browser = await self.pw.chromium.launch(headless=False)

        # [수정] HAR 레코딩 옵션 추가
        context = await self.browser.new_context(
            record_har_path=self.har_path
        )

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
            # [중요] context를 닫아야 HAR 파일이 디스크에 완전히 기록됩니다.
            await context.close()
            await self.browser.close()
            await self.pw.stop()
            if self.display:
                self.display.stop()

    async def fetch_har(self) -> Dict[str, bytes]:
        """
        HAR 파일을 분석하여 헤더를 복제하고, httpx로 요청을 재현하여
        컨텐츠를 바이트 배열(bytes)로 획득합니다.
        """
        self._entries = {}

        if not os.path.exists(self.har_path):
            logger.error("HAR 파일이 존재하지 않습니다.")
            return self._entries

        try:
            with open(self.har_path, 'r', encoding='utf-8') as f:
                har_data = json.load(f)
        except Exception as e:
            logger.error(f"HAR 파싱 실패: {e}")
            return self._entries

        self._entries = har_data.get('log', {}).get('entries', [])
        logger.info(f"HAR 분석 시작: 총 {len(self._entries)}개의 트랜잭션 발견")
        return self._entries

    async def get_bytes(self, patterns: List[str] = None) -> Dict[str, bytes]:

        results = {}

        if not self._entries:
            await self.fetch_har()

        for pattern in patterns or []:
            self._entries = [e for e in self._entries if re.search(pattern, e.get('request', {}).get('url', ''))]

        for entry in self._entries:
            request = entry.get('request', {})
            url = request.get('url')
            method = request.get('method')

            # 1. 유효하지 않은 URL 필터링 (Data URI, Non-HTTP)
            if not url or url.startswith('data:') or not url.startswith('http'):
                continue

            # 2. 헤더 복제 (Host, Content-Length 등 충돌 우려 헤더 제외)
            # httpx가 자동으로 처리하는 헤더는 제외해야 안전합니다.
            exclude_headers = {'host', 'content-length', 'connection', 'accept-encoding'}
            headers = {
                h['name']: h['value']
                for h in request.get('headers', [])
                if h['name'].lower() not in exclude_headers
            }

            try:
                logger.info(f"데이터 획득 시도: {url}")

                # 3. httpx 요청 재현 (로그인된 세션/쿠키 사용)
                # stream=True 대신 직접 await하여 메모리에 적재
                resp = await self.http_client.request(method, url, headers=headers)

                if resp.status_code == 200:
                    # 4. 바이트 배열 획득 및 저장
                    content_bytes = resp.content
                    if results.get(url):
                        results[url].append(content_bytes)
                    else:
                        results[url] = [content_bytes]
                    logger.info(f"  -> 획득 성공 ({len(content_bytes)} bytes)")
                else:
                    logger.warning(f"  -> 실패 Status: {resp.status_code}")

            except Exception as e:
                logger.error(f"  -> 요청 오류: {e}")

        return results

    async def extract_meta(self, url: str, max_retries: int = 2) -> Dict[str, Any]:
        for attempt in range(max_retries + 1):
            try:
                resp = await self.http_client.get(url)
                resp.raise_for_status()
                return self.parse_html(resp.text)
            except Exception as e:
                if attempt == max_retries:
                    return {"error": str(e)}
                await asyncio.sleep(0.5)
        return {}

    def parse_html(self, html: str) -> Dict[str, Any]:
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

        # 1. 로그인 수행 및 통신 기록 (HAR 저장)
        await client.login_and_dump_cookies(url, "tester", "password")

        logger.info("--- Phase 2: Replay & Fetch Bytes ---")
        # 2. HAR 기반으로 요청 재현하여 바이트 데이터 획득 (Disk 저장 X)
        fetched_data = await client.get_bytes()

        logger.info(f"총 {len(fetched_data)}개의 리소스 데이터를 메모리에 확보했습니다.")

        # 예시: 확보된 데이터 확인 (상위 3개만 로그 출력)
        for i, (res_url, data) in enumerate(fetched_data.items()):
            if i >= 3: break
            logger.info(f"URL: {res_url} | Size: {len(data)} bytes | Preview: {next(iter(data))[:20]}...")

        meta_user = client.parse_html(fetched_data['http://127.0.0.1:5000/'][0])
        for k, v in meta_user.items():
            logger.info(f"[{k:<12}] {v}")

    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        logger.info("Stopped.")
