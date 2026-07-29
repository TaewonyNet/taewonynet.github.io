"""
웹 클라이언트 4종(requests·httpx·playwright·HAR) 비교 하니스.

같은 데모 서버에서 동일한 메타(title·description·og:*)를 추출하고
실행 시간을 비교한다. 앞선 글들의 src/webclient_*.py 를 그대로 재사용한다.

같은 디렉터리(src/)에서 실행한다. (각 모듈이 sibling import 를 사용)
"""

import asyncio
import importlib
import logging
import sys
import time

logging.basicConfig(
    level=logging.WARNING,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WebClientCompare")
logger.setLevel(logging.INFO)

import demoserver

URL = "http://127.0.0.1:5000"


def bench_sync(label: str, make_client) -> tuple:
    """동기 클라이언트의 메타 추출 시간을 측정한다."""
    client = make_client()
    start = time.perf_counter()
    meta = client.extract_meta(URL)
    return label, time.perf_counter() - start, meta


async def bench_async(label: str, make_client, needs_browser: bool = False) -> tuple:
    """비동기 클라이언트의 메타 추출 시간을 측정한다."""
    client = make_client()
    if needs_browser:
        await client.init_browser()
    try:
        start = time.perf_counter()
        meta = await client.extract_meta(URL)
        return label, time.perf_counter() - start, meta
    finally:
        if hasattr(client, "close"):
            await client.close()


async def main():
    demoserver.run(is_while=False)
    results = []

    # requests — 동기, 가장 가벼움
    rq = importlib.import_module("webclient_rq")
    results.append(bench_sync("requests", lambda: rq.WebClient()))

    # httpx — 비동기
    htx = importlib.import_module("webclient_htx")
    results.append(await bench_async("httpx", lambda: htx.WebClient()))

    # playwright — 실제 브라우저
    pw = importlib.import_module("webclient_pw")
    results.append(await bench_async("playwright", lambda: pw.WebClient(), needs_browser=True))

    # 결과 비교 출력
    print(f"\n{'클라이언트':<12} {'시간(s)':>10}  메타 키")
    print("-" * 52)
    for label, elapsed, meta in results:
        keys = ",".join(k for k in meta if k != "error") or "(없음)"
        print(f"{label:<12} {elapsed:>10.4f}  {keys}")

    print("\n* HAR 방식은 로그인·기록·재현의 별도 흐름이므로 src/webclient_har.py 참고.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped.")
