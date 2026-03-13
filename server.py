#!/usr/bin/env python3
"""
image-analyzer server
Serves static files + proxies Claude API calls to avoid CORS.
Usage: ANTHROPIC_API_KEY=sk-... python3 server.py
"""

import http.server
import json
import os
import urllib.request
import urllib.error
from pathlib import Path


def load_dotenv(path=".env"):
    """Load key=value pairs from a .env file into os.environ."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip().strip("\"'"))
    except FileNotFoundError:
        pass

PORT = 8788
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} — {fmt % args}")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path == "/analyze":
            self._handle_analyze()
        else:
            self.send_error(404)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Api-Key")

    def _handle_analyze(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json_error(400, "Invalid request body")
            return

        # API key: read from environment only
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            self._json_error(401, "ANTHROPIC_API_KEY is not set. Start the server with: ANTHROPIC_API_KEY=sk-ant-... python3 server.py")
            return

        image_b64 = body.get("image")
        media_type = body.get("mediaType", "image/jpeg")
        prompt = body.get("prompt", "Identify and describe what is in this image in detail. Include: what it is, key characteristics, context, and any interesting facts.")

        if not image_b64:
            self._json_error(400, "No image provided")
            return

        # Build Claude request
        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }

        req = urllib.request.Request(
            CLAUDE_API_URL,
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
                text = result["content"][0]["text"]
                self._json_ok({"result": text})
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                msg = err_body
            self._json_error(e.code, msg)
        except Exception as e:
            self._json_error(500, str(e))

    def _json_ok(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, code, message):
        body = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    load_dotenv()
    print(f"\n  🔍 Image Analyzer server → http://localhost:{PORT}/image-analyzer.html")
    key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    if not key_set:
        print("  ⚠️  ANTHROPIC_API_KEY is not set!")
        print("  ➜  Restart with: ANTHROPIC_API_KEY=sk-ant-... python3 server.py\n")
    else:
        print("  🔑 API key: ✅ ready\n")
    server = http.server.HTTPServer(("", PORT), Handler)
    server.serve_forever()
