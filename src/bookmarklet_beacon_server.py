"""
북마크릿 → Beacon 수신 서버 최소 구현.

JS_BOOKMARKLET은 navigator.sendBeacon으로 현재 페이지 title과 URL을
/collect 엔드포인트로 전송하는 북마크릿이다. Flask 서버는 이를 받아
메모리 리스트에 쌓는다. 어느 기기의 브라우저에서 실행해도 같은
엔드포인트로 데이터가 모인다는 것을 이 서버 하나로 확인할 수 있다.
"""

import logging
import threading
import time

import requests
from flask import Flask, request

app = Flask(__name__)
log = logging.getLogger("bookmarklet_beacon_server")

COLLECTED: list[dict] = []

JS_BOOKMARKLET = """
(function () {
    var payload = JSON.stringify({
        title: document.title,
        url: location.href,
        ts: Date.now()
    });
    navigator.sendBeacon("http://127.0.0.1:PORT/collect", payload);
})();
""".strip()


@app.route("/collect", methods=["POST"])
def collect():
    body = request.get_data(as_text=True)
    COLLECTED.append({"body": body, "remote_addr": request.remote_addr})
    return "", 204


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run(port: int | None = None) -> str:
    if port is None:
        port = _free_port()
    t = threading.Thread(
        target=lambda: app.run(port=port, debug=False, use_reloader=False, threaded=True),
        daemon=True,
    )
    t.start()
    time.sleep(1.0)
    return f"http://127.0.0.1:{port}"


def main() -> None:
    base = run()
    port = base.rsplit(":", 1)[1]
    bookmarklet = JS_BOOKMARKLET.replace("PORT", port)
    print("생성된 북마크릿(발췌):")
    print(bookmarklet[:120] + "...")

    # 실제 브라우저의 sendBeacon 대신, 같은 body를 requests로 재현해 서버 수신을 확인한다.
    fake_payload = '{"title": "테스트 페이지", "url": "http://example.test", "ts": 1234567890}'
    r = requests.post(
        f"{base}/collect",
        data=fake_payload.encode("utf-8"),
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    print(f"\n/collect 응답 status={r.status_code} 누적건수={len(COLLECTED)}")
    print(f"수신 내용: {COLLECTED[-1]}")


if __name__ == "__main__":
    main()
