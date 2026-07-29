"""
CORS 데모 — 헤더 유무·Beacon 경로 비교.

Flask로 세 엔드포인트를 띄운다.
- /no-cors : Access-Control-Allow-Origin 헤더 없음
- /with-cors : Access-Control-Allow-Origin: * 포함
- /beacon (POST) : navigator.sendBeacon 이 도달할 자리를 흉내낸 수신 라우트

CORS는 브라우저가 응답을 "읽어도 되는지" 판단하는 정책이지, 서버가 요청 자체를
막는 정책이 아니다. 이 데모는 서버 쪽에서 그 사실을 확인한다 — 파이썬 클라이언트는
브라우저가 아니므로 헤더 유무와 무관하게 두 엔드포인트 모두 응답을 받는다. 실제
브라우저 fetch였다면 /no-cors 응답은 도달은 하되 JS가 내용을 읽지 못했을 자리다.
"""

import logging
import threading
import time

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)
log = logging.getLogger("cors_bypass_demo")

BEACON_LOG: list[dict] = []


@app.route("/no-cors")
def no_cors():
    """CORS 헤더가 없는 응답 — 브라우저 fetch라면 여기서 차단된다."""
    return jsonify({"ok": True, "endpoint": "no-cors"})


@app.route("/with-cors")
def with_cors():
    """Access-Control-Allow-Origin: * 를 포함한 응답."""
    resp = jsonify({"ok": True, "endpoint": "with-cors"})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.route("/beacon", methods=["POST"])
def beacon():
    """navigator.sendBeacon 이 도달할 자리. CORS 헤더 없이도 수신만 하면 된다."""
    body = request.get_data(as_text=True)
    BEACON_LOG.append({"body": body, "content_type": request.content_type})
    return "", 204


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def run(port: int | None = None) -> str:
    """데모 서버를 데몬 스레드로 띄운다."""
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
    print(f"서버 기동: {base}")

    r1 = requests.get(f"{base}/no-cors")
    print(f"/no-cors    status={r1.status_code} ACAO헤더={r1.headers.get('Access-Control-Allow-Origin')}")

    r2 = requests.get(f"{base}/with-cors")
    print(f"/with-cors  status={r2.status_code} ACAO헤더={r2.headers.get('Access-Control-Allow-Origin')}")

    r3 = requests.post(f"{base}/beacon", data="hello-from-beacon", headers={"Content-Type": "text/plain"})
    print(f"/beacon     status={r3.status_code} 수신건수={len(BEACON_LOG)}")

    print(
        "\n결론: 서버 관점에서는 헤더 유무와 무관하게 요청이 항상 도달한다. "
        "차단은 브라우저가 응답을 읽는 단계에서만 일어난다."
    )


if __name__ == "__main__":
    main()
