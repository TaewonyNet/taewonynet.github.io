import socket
import requests
import threading
import time
import re
from bs4 import BeautifulSoup
from flask import Flask, request, session, redirect, jsonify, render_template_string
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("DemoServer")

class DemoServer:
    """
    A simple Flask server to demonstrate metadata changes based on login state.
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
    </head>
    <body>
        <h1>Demo Page</h1>
        {% if 'user' in session %}
            <p>Status: Logged In ({{ session['user'] }})</p>
            <a href="/logout">Logout</a>
        {% else %}
            <p>Status: Guest</p>
            <form method="post" action="/login">
                <input type="text" name="id" value="user" required>
                <input type="password" name="pw" value="pass" required>
                <button type="submit">Login</button>
            </form>
        {% endif %}
    </body>
    </html>
    """

    def __init__(self, port: int = 5000):
        self.port = port
        self.app = Flask(__name__)
        self.app.secret_key = "secret-key-for-demo"
        self._register_routes()

    def _register_routes(self):
        @self.app.route('/', methods=['GET'])
        def index():
            if 'user' in session:
                ctx = {
                    "title": "My Account",
                    "desc": "User Dashboard",
                    "og_title": "My Account - Logged In",
                    "og_desc": "Active Session"
                }
            else:
                ctx = {
                    "title": "Login Page",
                    "desc": "Please login",
                    "og_title": "Login Required",
                    "og_desc": "Enter credentials"
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
        """Starts the Flask server in a daemon thread."""
        logger.info(f"Starting background server on port {self.port}...")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(0.3)
                s.bind(('0.0.0.0', self.port))
            except OSError:
                logger.warning("Port is already in use. Skipping.")
        # use_reloader=False is mandatory for thread execution
        t = threading.Thread(
            target=self.app.run,
            kwargs={'debug': False, 'use_reloader': False, 'port': self.port},
            daemon=True
        )
        t.start()
        time.sleep(1.5)  # Wait for server startup

def run(is_while: bool = True):
    port = 5000
    base_url = f"http://127.0.0.1:{port}"

    # Start Server
    server = DemoServer(port=port)
    server.run_in_thread()

    try:
        if is_while:
            logger.info("Server is still running. Press Ctrl+C to exit.")
            while True:
                time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Shutting down.")


if __name__ == "__main__":
    run(is_while=True)
