import logging
import socket
import sys
import threading
import time

from flask import Flask, request, session, redirect, render_template_string

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DemoServer")


class DemoServer:
    """
    메타데이터에 봇 감지 로그를 상세히 기록하는 데모 서버.
    기존 SEO/OG 태그를 유지하면서 감지 리포트를 description에 주입합니다.
    """

    HOME_HTML = """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="utf-8">
        <title>{{title}}</title>
        <meta name="description" content="{{desc}}">
        <meta property="og:title" content="{{og_title}}">
        <meta property="og:description" content="{{og_desc}}">

        <meta name="x-bot-status" content="{{is_bot}}">
        <meta name="x-detection-step" content="{{detection_log}}">
    </head>
    <body style="font-family: sans-serif; padding: 40px; text-align: center;">
        <h1>Welcome to Secure Portal</h1>
        <p>Current Status: <strong>{{ 'Authenticated' if 'user' in session else 'Guest' }}</strong></p>

        <hr style="width: 50%; margin: 30px auto;">

        {% if 'user' in session %}
            <p>Hello, {{ session['user'] }}! | <a href="/logout">Logout</a></p>
        {% else %}
            <form method="post" action="/login" style="display: inline-block; text-align: left; padding: 20px; border: 1px solid #ddd;">
                <div style="margin-bottom: 10px;">
                    ID: <input type="text" name="id" value="tester">
                </div>
                <div style="margin-bottom: 10px;">
                    PW: <input type="password" name="pw" value="password">
                </div>
                <button type="submit" style="width: 100%;">Login</button>
            </form>
        {% endif %}

        <script>
            // 브라우저 핑거프린팅 시뮬레이션
            if (navigator.webdriver) {
                console.warn("Automation detected via JS");
            }
        </script>
    </body>
    </html>
    """

    def __init__(self, port: int = 5000):
        self.port = port
        self.app = Flask(__name__)
        self.app.secret_key = "secure-meta-key"
        self._register_routes()

    def _analyze_request(self):
        """요청을 분석하여 가능한 많은 단서를 수집해 봇 여부를 판단"""
        headers = request.headers
        ua = headers.get('User-Agent', 'Unknown')
        steps = []

        # ── 1. User-Agent 기반 탐지 ────────────────────────────────────────
        ua_lower = ua.lower()
        if any(x in ua_lower for x in
               ["python", "requests", "httpx", "curl", "wget", "go-http", "okhttp", "axios", "cfnetwork"]):
            steps.append("[UA-Lib]")

        if "headless" in ua_lower or "phantom" in ua_lower or "slimer" in ua_lower:
            steps.append("[UA-Headless]")

        # ── 2. Client Hints (Modern Browser Fingerprint) ─────────────────────
        missing_hints = []
        for h in [
            "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
            "sec-ch-ua-full-version-list", "sec-ch-ua-platform-version"
        ]:
            if h not in headers:
                missing_hints.append(h)

        if missing_hints:
            steps.append(f"[Missing-CH:{','.join(missing_hints)}]")

        # ── 3. Fetch Metadata / Sec-Fetch-* ─────────────────────────────────
        if not headers.get("sec-fetch-site"):
            steps.append("[No-Sec-Fetch-Site]")
        if not headers.get("sec-fetch-mode"):
            steps.append("[No-Sec-Fetch-Mode]")
        if not headers.get("sec-fetch-dest"):
            steps.append("[No-Sec-Fetch-Dest]")

        # ── 4. 흔한 브라우저 필수 헤더 누락 ────────────────────────────────
        required = ["Accept", "Accept-Language", "Accept-Encoding"]
        missing_req = [h for h in required if h not in headers]
        if missing_req:
            steps.append(f"[Missing-Req-Hdr:{','.join(missing_req)}]")

        # ── 5. 비정상 Accept 헤더 패턴 ─────────────────────────────────────
        accept = headers.get("Accept", "")
        if accept and "*/*" in accept and "text/html" not in accept:
            steps.append("[Suspicious-Accept]")

        # ── 6. Referer / Origin 누락 패턴 (직접 접근 or API-like) ──────────
        if not headers.get("Referer") and not headers.get("Origin"):
            steps.append("[No-Referrer-No-Origin]")

        # ── 7. DNT (Do Not Track) 헤더가 없는 경우도 신호로 활용 가능 ─────
        if "DNT" not in headers:
            steps.append("[No-DNT]")  # 현대 브라우저 대부분 보냄

        # ── 8. Connection 헤더가 이상한 경우 ───────────────────────────────
        conn = headers.get("Connection", "").lower()
        if conn and conn not in ["keep-alive", "close"]:
            steps.append(f"[Strange-Connection:{conn}]")

        # ── 종합 판단 ───────────────────────────────────────────────────────
        is_bot = "Yes" if len(steps) >= 2 else "Maybe" if steps else "No"

        detection_log = " | ".join(steps) if steps else "Passed-All-Checks"
        if len(steps) >= 4:
            detection_log += " (HIGH CONFIDENCE BOT)"

        return ua, is_bot, detection_log

    def _register_routes(self):
        @self.app.route('/')
        def index():
            ua, is_bot, detection_log = self._analyze_request()

            # 메타데이터 구성
            title = "Secure Dashboard" if 'user' in session else "Login Required"

            short_ua = ua[:80] + "…" if len(ua) > 80 else ua

            desc_report = (
                f"BotStatus: {is_bot} | "
                f"UA: {short_ua} | "
                f"Log: {detection_log} | "
                f"IP: {request.remote_addr} | "
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

            ctx = {
                "title": title,
                "desc": desc_report,
                "og_title": f"Portal - {title}",
                "og_desc": "Secure session-based metadata access control.",
                "is_bot": is_bot,
                "detection_log": detection_log,
                "ua": ua
            }
            return render_template_string(self.HOME_HTML, **ctx)

        @self.app.route('/login', methods=['POST'])
        def login():
            session['user'] = request.form.get('id', 'unknown')
            return redirect('/')

        @self.app.route('/logout')
        def logout():
            session.pop('user', None)
            return redirect('/')

    def run_in_thread(self):
        logger.info(f"DemoServer started on port {self.port} (Monitoring via Metadata)")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(0.3)
                s.bind(('0.0.0.0', self.port))
            except OSError:
                logger.warning("Port is already in use. Skipping.")
        t = threading.Thread(
            target=self.app.run,
            kwargs={'debug': False, 'use_reloader': False, 'port': self.port, 'host': '0.0.0.0'},
            daemon=True
        )
        t.start()
        time.sleep(1)


def run(is_while: bool = True):
    server = DemoServer()
    server.run_in_thread()
    if is_while:
        try:
            while True: time.sleep(10)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    run(is_while=True)