#!/usr/bin/env python3
"""
셀레니움 퍼포먼스 로그로 네트워크 요청을 캡처해 동영상 스트림 URL을 잡는다.

Chrome DevTools Performance 로그를 활성화한 뒤 페이지를 열면
브라우저가 실제로 요청한 모든 URL이 기록된다. 이 중 video/* MIME 타입이거나
.m3u8/.mpd/.mp4/.webm 확장자를 가진 URL을 추출한다.

DOM에 src가 노출되지 않는 HLS·DASH 스트림도 잡을 수 있다.
  - mp4/webm: requests로 직접 다운로드
  - m3u8(HLS): ffmpeg으로 다운로드 (ffmpeg 설치 필요)

requirements: selenium, webdriver-manager, requests
optional: ffmpeg (HLS 다운로드 시)
"""

import json
import logging
import pathlib
import subprocess
import sys
import time

import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("NetworkCapture")

VIDEO_EXTS = {".mp4", ".webm", ".m3u8", ".mpd", ".ts"}
CHUNK = 1024 * 1024  # 1 MB


def _make_driver(headless: bool = True) -> webdriver.Chrome:
    """퍼포먼스 로그를 활성화한 Chrome 드라이버를 반환한다."""
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    if headless:
        options.add_argument("--headless=new")

    # 퍼포먼스 로그 활성화 — 네트워크 요청 전체 기록
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    try:
        return webdriver.Chrome(service=Service("chromedriver"), options=options)
    except Exception:
        from webdriver_manager.chrome import ChromeDriverManager
        return webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )


def capture_video_urls(driver: webdriver.Chrome) -> list[dict]:
    """
    퍼포먼스 로그에서 video 관련 URL을 수집한다.
    반환: [{"url": ..., "mime": ..., "size": ...}, ...]
    """
    found: dict[str, dict] = {}
    for entry in driver.get_log("performance"):
        try:
            msg = json.loads(entry["message"])["message"]
        except (KeyError, json.JSONDecodeError):
            continue

        if msg.get("method") != "Network.responseReceived":
            continue

        resp = msg["params"]["response"]
        url: str = resp.get("url", "")
        mime: str = resp.get("mimeType", "")
        size: int = resp.get("encodedDataLength", 0)

        ext = pathlib.Path(url.split("?")[0]).suffix.lower()
        if "video" in mime or "mpegurl" in mime or ext in VIDEO_EXTS:
            found[url] = {"url": url, "mime": mime, "size": size}

    return list(found.values())


def download_direct(url: str, dest: pathlib.Path, timeout: int = 60) -> pathlib.Path:
    """mp4/webm 직접 다운로드."""
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


def download_hls(m3u8_url: str, dest: pathlib.Path) -> pathlib.Path:
    """HLS 스트림 — ffmpeg으로 전체 세그먼트를 합쳐 저장한다."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", m3u8_url,
        "-c", "copy",
        str(dest),
    ]
    logger.info(f"ffmpeg 실행: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{result.stderr[-500:]}")
    logger.info(f"완료: {dest}")
    return dest


def fetch_stream(page_url: str, output_dir: str = "downloads",
                 headless: bool = True, wait: float = 3.0) -> pathlib.Path | None:
    """
    page_url 페이지를 열어 네트워크 로그에서 video URL을 찾아 내려받는다.
    성공 시 저장된 경로 반환, 실패 시 None.
    """
    driver = _make_driver(headless=headless)
    try:
        logger.info(f"페이지 열기: {page_url}")
        driver.get(page_url)
        time.sleep(wait)  # 스트림 세그먼트 요청 발생 대기

        hits = capture_video_urls(driver)
        if not hits:
            logger.warning("video URL을 찾지 못했음")
            return None

        for h in hits:
            logger.info(f"  {h['mime']:30s}  {h['url'][:80]}")

        target = hits[0]["url"]
        ext = pathlib.Path(target.split("?")[0]).suffix.lower() or ".mp4"
        dest = pathlib.Path(output_dir) / f"stream{ext}"

        if ext == ".m3u8":
            return download_hls(target, dest.with_suffix(".mp4"))
        return download_direct(target, dest)
    finally:
        driver.quit()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else \
        "https://www.w3schools.com/html/html5_video.asp"
    result = fetch_stream(url, headless=True)
    print("저장:", result if result else "실패")
    sys.exit(0 if result else 1)
