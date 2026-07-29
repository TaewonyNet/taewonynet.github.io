"""
하이브리드 클라이언트 시연용 랜덤 데모 서버.

요청마다 무작위로 두 종류의 페이지를 돌려준다.
- static: <title>·og 태그가 HTML에 그대로 있어 httpx로 충분.
- spa   : 빈 셸 + JS로 제목/메타를 런타임 생성 → httpx로는 미흡, playwright 필요.

이 무작위성 덕에 같은 URL이라도 하이브리드가 httpx / httpx→playwright 를 오가는 것을
관찰할 수 있다.
"""

import logging
import random
import threading

from flask import Flask

app = Flask(__name__)
log = logging.getLogger("demoserver_random")

STATIC_PAGE = """<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<title>정적 렌더 페이지</title>
<meta property="og:title" content="정적 OG 타이틀">
<meta property="og:description" content="HTML에 그대로 담긴 메타라 httpx로 충분하다.">
</head><body>
<h1>서버가 완성된 HTML을 그대로 돌려준 경우</h1>
<p>본문이 충분히 길어 httpx 단계에서 메타 추출이 끝난다. {pad}</p>
</body></html>""".format(pad="가" * 300)

# 빈 셸 — title/og 가 없고 본문은 JS가 그린다 (500바이트 미만)
SPA_PAGE = """<!doctype html><html><head><meta charset="utf-8"></head>
<body><div id="app"></div>
<script>
document.title = "JS 렌더 페이지";
var m = document.createElement('meta');
m.setAttribute('property','og:title'); m.content = 'JS OG 타이틀';
document.head.appendChild(m);
document.getElementById('app').innerHTML = '<h1>브라우저가 실행해야 보이는 본문</h1>';
</script></body></html>"""


@app.route("/")
def index():
    if random.random() < 0.5:
        log.info("served: static")
        return STATIC_PAGE
    log.info("served: spa")
    return SPA_PAGE


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run(port: int | None = None):
    """데모 서버를 데몬 스레드로 띄운다. port 미지정 시 빈 포트 자동 선택."""
    if port is None:
        port = _free_port()
    t = threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False, threaded=True),
        daemon=True,
    )
    t.start()
    import time
    time.sleep(1.0)  # 기동 대기
    return f"http://127.0.0.1:{port}"


if __name__ == "__main__":
    url = run()
    print("running:", url)
    import time
    time.sleep(60)
