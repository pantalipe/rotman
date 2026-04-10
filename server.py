"""
Rotman HTTP server — serves the UI and REST API.
Pure stdlib, no Flask/FastAPI.
"""
import json
import os
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import pipeline as pl

UI_DIR = os.path.join(os.path.dirname(__file__), "ui")
OUTPUT_ROOT = os.path.join(os.path.dirname(__file__), "output")

HOST = "localhost"
PORT = 7070


class RotmanHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[server] {self.address_string()} {format % args}")

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        if path in ("", "/"):
            self._serve_file(os.path.join(UI_DIR, "index.html"))

        elif path == "/api/projects":
            self._json(pl.get_projects())

        elif path.startswith("/api/projects/"):
            parts = path.split("/")

            # GET /api/projects/<id>
            if len(parts) == 4:
                p = pl.get_project(parts[3])
                self._json(p) if p else self._not_found()

            # GET /api/projects/<id>/video
            elif len(parts) == 5 and parts[4] == "video":
                p = pl.get_project(parts[3])
                if p and p.get("video_path") and os.path.exists(p["video_path"]):
                    self._serve_file(p["video_path"])
                else:
                    self._not_found()
            else:
                self._not_found()
        else:
            self._not_found()

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/")

        # POST /api/projects
        if path == "/api/projects":
            body = self._read_json()
            topic = body.get("topic", "").strip()
            channel = body.get("channel", "general")
            if not topic:
                self._error(400, "topic required")
                return
            project_id = pl.create_project(topic, channel)
            self._json({"id": project_id}, status=201)

        # POST /api/projects/<id>/retry
        elif path.startswith("/api/projects/") and path.endswith("/retry"):
            parts = path.split("/")
            if len(parts) == 5:
                project_id = parts[3]
                ok = pl.retry_project(project_id)
                self._json({"ok": ok}) if ok else self._error(400, "Cannot retry this project")
            else:
                self._not_found()
        else:
            self._not_found()

    def do_DELETE(self):
        path = urlparse(self.path).path.rstrip("/")
        parts = path.split("/")

        # DELETE /api/projects/<id>
        if path.startswith("/api/projects/") and len(parts) == 4:
            ok = pl.delete_project(parts[3])
            self._json({"ok": ok}) if ok else self._not_found()
        else:
            self._not_found()

    # ── HELPERS ─────────────────────────────────────────────────────────
    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, filepath):
        if not os.path.exists(filepath):
            self._not_found()
            return
        mime, _ = mimetypes.guess_type(filepath)
        mime = mime or "application/octet-stream"
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _not_found(self):
        self._error(404, "not found")

    def _error(self, status, msg):
        body = json.dumps({"error": msg}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run():
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "db"), exist_ok=True)
    server = HTTPServer((HOST, PORT), RotmanHandler)
    print(f"[rotman] Running at http://{HOST}:{PORT}")
    print(f"[rotman] Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[rotman] Stopped.")


if __name__ == "__main__":
    run()
