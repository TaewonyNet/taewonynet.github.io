import logging
import random
import sys
import time
from typing import Dict, Optional, List, Any

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WebMetaApp")

from dependency import dependency_check

dependency_check({
    "flask": "flask",
    "requests": "requests",
    "bs4": "beautifulsoup4",
})
DEFAULT_USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

import requests
from bs4 import BeautifulSoup


class WebClient:
    def __init__(self, user_agents: Optional[List[str]] = None, timeout: int = 10):
        self.user_agents = user_agents or DEFAULT_USER_AGENTS
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'User-Agent': random.choice(self.user_agents)
        })

    def login(self, url: str, username: str, password: str):
        self.session.post(f"{url}/login", data={"id": username, "pw": password})

    def extract_meta(self, url: str, max_retries: int = 2) -> Dict[str, Any]:
        for attempt in range(max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return self._parse_html(resp.text)
            except requests.RequestException as e:
                if attempt == max_retries:
                    return {"error": str(e)}
                time.sleep(0.5)
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


def run_test():
    import demoserver
    url = "http://127.0.0.1:5000"
    demoserver.run(is_while=False)

    client = WebClient()

    logger.info("--- Phase 1: Guest ---")
    meta_guest = client.extract_meta(url)
    for k, v in meta_guest.items():
        logger.info(f"[{k:<12}] {v}")

    logger.info("--- Phase 2: User ---")
    client.login(url, "tester", "password")
    meta_user = client.extract_meta(url)
    for k, v in meta_user.items():
        logger.info(f"[{k:<12}] {v}")


if __name__ == "__main__":
    try:
        run_test()
    except KeyboardInterrupt:
        logger.info("Stopped.")
