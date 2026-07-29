"""
수집 전략 자동 선택 하이브리드 클라이언트.

가벼운 httpx로 먼저 시도하고, 결과가 미흡(JS 렌더링·차단 의심)하면 playwright로
에스컬레이션한다. 도메인별로 "성공한 전략"을 기억해 다음부터는 그 전략으로 바로 시작한다.

앞 글들의 webclient_htx/webclient_pw 와 같은 메타 추출을 공유한다.
requirements: httpx, playwright, beautifulsoup4
"""

import asyncio
import logging
import sys
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger("HybridClient")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def parse_meta(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    meta = {}
    if title := soup.find("title"):
        meta["title"] = title.get_text(strip=True)
    for prop in ["og:title", "og:description", "og:image", "og:url"]:
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if tag:
            meta[prop.replace("og:", "og_")] = tag.attrs.get("content", "").strip()
    return meta


def needs_escalation(html: str, status: int) -> bool:
    """httpx 결과가 미흡한지 판정 — 차단·빈 본문·JS 의존 신호."""
    if status >= 400:
        return True
    if not html or len(html) < 500:
        return True
    low = html.lower()
    # 본문이 거의 없고 스크립트만 있는 SPA 신호
    if "<title" not in low and "og:title" not in low:
        return True
    if any(s in low for s in ["just a moment", "verify you are human", "enable javascript"]):
        return True
    return False


class HybridClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.http = httpx.AsyncClient(headers={"User-Agent": UA},
                                      timeout=timeout, follow_redirects=True)
        self.strategy_cache: dict[str, str] = {}  # domain -> "httpx" | "playwright"

    def _domain(self, url: str) -> str:
        return urlparse(url).netloc

    async def _via_httpx(self, url: str):
        try:
            r = await self.http.get(url)
            return r.text, r.status_code
        except Exception as e:
            logger.warning(f"httpx 실패: {e}")
            return "", 599

    async def _via_playwright(self, url: str) -> str:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await (await browser.new_context(user_agent=UA)).new_page()
                await page.goto(url, wait_until="domcontentloaded")
                return await page.content()
            finally:
                await browser.close()

    async def fetch(self, url: str) -> dict:
        domain = self._domain(url)
        cached = self.strategy_cache.get(domain)

        # 캐시된 전략이 playwright면 바로 브라우저로
        if cached == "playwright":
            html = await self._via_playwright(url)
            return {**parse_meta(html), "_strategy": "playwright(cached)"}

        # 기본: httpx 먼저
        html, status = await self._via_httpx(url)
        if not needs_escalation(html, status):
            self.strategy_cache[domain] = "httpx"
            return {**parse_meta(html), "_strategy": "httpx"}

        # 미흡 → playwright로 에스컬레이션 + 도메인 전략 학습
        logger.info(f"에스컬레이션: {domain} → playwright")
        html = await self._via_playwright(url)
        self.strategy_cache[domain] = "playwright"
        return {**parse_meta(html), "_strategy": "httpx→playwright"}

    async def close(self):
        await self.http.aclose()


async def main():
    import demoserver_random
    url = demoserver_random.run()  # 요청마다 static/spa 무작위

    client = HybridClient()
    try:
        # 같은 URL이라도 응답이 무작위라 전략이 바뀌는 걸 보이려 매 회 캐시를 비운다.
        for i in range(8):
            client.strategy_cache.clear()
            r = await client.fetch(url)
            print(f"{i+1}회차  전략={r.get('_strategy'):<18} title={r.get('title')}")
    finally:
        await client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped.")
