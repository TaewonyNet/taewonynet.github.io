#!/usr/bin/env python3
"""
셀레니움으로 동영상 사이트에서 영상 URL을 추출해 내려받는다.

Driver 클래스로 페이지를 열고 <video> 태그에서 재생 가능한 URL을 찾아
requests로 청크 다운로드한다. 세 가지 추출 경로를 순서대로 시도한다.
  1. <video src="...">
  2. <video><source src="...">
  3. JS 글로벌 변수 (window.__videoUrl 등)

requirements: selenium, webdriver-manager, requests
"""

import logging
import pathlib
import sys
import time

import requests
from selenium.webdriver.common.by import By

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from selenium_driver import Driver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("VideoDownload")

CHUNK = 1024 * 1024  # 1 MB
JS_KEYS = ["__videoUrl", "videoSrc", "mediaUrl", "videoUrl"]


def extract_video_urls(driver) -> list[str]:
    """페이지에서 재생 가능한 video URL을 모두 수집한다."""
    urls: list[str] = []

    # 1. <video src="..."> — Selenium이 상대 URL을 절대 URL로 반환
    for el in driver.find_elements(By.CSS_SELECTOR, "video[src]"):
        src = el.get_attribute("src") or ""
        if src.startswith("http"):
            urls.append(src)

    # 2. <video><source src="..."></video>
    for el in driver.find_elements(By.CSS_SELECTOR, "video source[src]"):
        src = el.get_attribute("src") or ""
        if src.startswith("http"):
            urls.append(src)

    # 3. JS 글로벌 변수 — 동적 렌더링 사이트에서 src가 스크립트로 주입될 때
    for key in JS_KEYS:
        try:
            val = driver.execute_script(f"return window['{key}']")
            if isinstance(val, str) and val.startswith("http"):
                urls.append(val)
        except Exception:
            pass

    return list(dict.fromkeys(urls))  # 순서 보존 dedup


def download(url: str, dest: pathlib.Path, timeout: int = 60) -> pathlib.Path:
    """청크 단위로 스트림을 받아 파일로 저장한다."""
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    with requests.get(url, headers=headers, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        received = 0
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK):
                f.write(chunk)
                received += len(chunk)
                if total:
                    pct = received * 100 // total
                    print(f"\r  {pct:3d}%  {received/1024/1024:.1f}/{total/1024/1024:.1f} MB",
                          end="", flush=True)
        print()
    logger.info(f"완료: {dest}  ({received/1024/1024:.1f} MB)")
    return dest


def fetch_video(page_url: str, output_dir: str = "downloads",
                headless: bool = True, wait: float = 2.0) -> pathlib.Path | None:
    """
    page_url 페이지를 열어 첫 번째 video URL을 내려받는다.
    성공 시 저장된 경로 반환, 실패 시 None.
    """
    driver = Driver(headless=headless)
    try:
        logger.info(f"페이지 열기: {page_url}")
        driver.get(page_url)
        driver.wait_for_load()
        driver.suppress_dialogs()
        time.sleep(wait)  # JS 렌더링 대기

        urls = extract_video_urls(driver)
        if not urls:
            logger.warning("video URL을 찾지 못했음")
            return None

        logger.info(f"발견 {len(urls)}개: {urls[0]}")
        target = urls[0]
        ext = target.split("?")[0].rsplit(".", 1)[-1] or "mp4"
        dest = pathlib.Path(output_dir) / f"video.{ext}"
        return download(target, dest)
    finally:
        driver.quit()


if __name__ == "__main__":
    # 인자 없으면 공개 샘플 페이지로 테스트
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.w3schools.com/html/html5_video.asp"
    result = fetch_video(url, headless=True)
    print("저장:", result if result else "실패")
    sys.exit(0 if result else 1)
