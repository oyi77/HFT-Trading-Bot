import json
import signal
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from trading_bot.interface.base import BaseInterface, InterfaceConfig


class WebInterface(BaseInterface):
    def __init__(
        self,
        config: Optional[InterfaceConfig] = None,
        host: str = "127.0.0.1",
        port: int = 8080,
    ):
        super().__init__(config)
        self.host = host
        self.port = port
        self.server: Optional[ThreadingHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.logs = []
        self.metrics = {
            "price": 0.0,
            "balance": config.balance if config else 100.0,
            "equity": config.balance if config else 100.0,
            "pnl": 0.0,
            "trades": 0,
            "positions": [],
        }

    def log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            self.logs.append({"time": timestamp, "level": level, "message": message})
            if len(self.logs) > 200:
                self.logs = self.logs[-200:]

    def update_metrics(self, metrics: dict):
        with self._lock:
            self.metrics.update(metrics)

    def _make_handler(self):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, payload, code=200):
                body = json.dumps(payload, default=str).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/health":
                    return self._json({"ok": True, "running": parent.running})
                if self.path == "/metrics":
                    with parent._lock:
                        return self._json(parent.metrics)
                if self.path == "/logs":
                    with parent._lock:
                        return self._json(parent.logs[-100:])
                if self.path == "/":
                    html = (
                        "<html><head><title>Trading Bot</title></head><body>"
                        "<h1>Trading Bot Web Interface</h1>"
                        "<p>Endpoints: <code>/health</code>, <code>/metrics</code>, <code>/logs</code></p>"
                        "</body></html>"
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(html)))
                    self.end_headers()
                    self.wfile.write(html)
                    return
                self._json({"error": "not found"}, 404)

            def log_message(self, format, *args):
                return

        return Handler

    def run(self):
        self.running = True

        def signal_handler(sig, frame):
            self.stop()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.server = ThreadingHTTPServer((self.host, self.port), self._make_handler())
        self.server_thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.server_thread.start()

        self.log(f"Web interface serving on http://{self.host}:{self.port}", "info")

        try:
            webbrowser.open(f"http://{self.host}:{self.port}", new=2)
        except Exception:
            pass

        if self.on_start_callback:
            self.on_start_callback(self.config)

        while self.running:
            threading.Event().wait(0.1)

    def stop(self):
        if not self.running:
            return
        self.running = False
        if self.on_stop_callback:
            self.on_stop_callback()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2)
        self.server_thread = None
