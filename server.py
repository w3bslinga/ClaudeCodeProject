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
CLAUDE_MODEL = "claude-opus-4-6"


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
        elif self.path == "/chat":
            self._handle_chat()
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
            "system": (
                "You are an image analysis assistant. Analyze images thoroughly and helpfully. "
                "IMPORTANT: If the image contains nudity, sexual content, explicit material, "
                "gore, or other inappropriate content, you MUST respond with exactly this format: "
                "[BLOCKED] This image contains content that I'm not able to analyze. "
                "Please try a different image that's appropriate for all audiences. "
                "Do NOT provide any analysis of inappropriate images."
            ),
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

    def _handle_chat(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json_error(400, "Invalid request body")
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            self._json_error(401, "ANTHROPIC_API_KEY is not set.")
            return

        image_b64 = body.get("image")
        media_type = body.get("mediaType", "image/jpeg")
        messages = body.get("messages", [])
        prompt = body.get("prompt", "")

        if not image_b64 or not prompt:
            self._json_error(400, "Missing image or prompt")
            return

        # Build messages: first message has the image, rest are text-only conversation
        api_messages = []

        # First user message with image + initial analysis prompt
        first_user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_b64,
                },
            },
        ]
        # If there's history, the first entry is the initial analysis prompt
        if messages and messages[0].get("role") == "user":
            first_user_content.append({"type": "text", "text": messages[0]["content"]})
            api_messages.append({"role": "user", "content": first_user_content})
            # Add remaining history
            for msg in messages[1:]:
                api_messages.append({"role": msg["role"], "content": msg["content"]})
        else:
            first_user_content.append({"type": "text", "text": "Analyze this image."})
            api_messages.append({"role": "user", "content": first_user_content})
            for msg in messages:
                api_messages.append({"role": msg["role"], "content": msg["content"]})

        # Add the new follow-up question
        api_messages.append({"role": "user", "content": prompt})

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "system": (
                "You are an image analysis assistant having a follow-up conversation about an image. "
                "You can see the image in the first message. Answer questions about the image and "
                "the analysis you provided. "
                "If the user asks something UNRELATED to the image or its analysis, respond with: "
                "\"Thanks for your curiosity! I'm here to help with questions about this image and "
                "its analysis. Feel free to ask me anything about what you see!\" "
                "If the user asks an inappropriate, sexual, or offensive question, respond with: "
                "\"I'd love to keep chatting, but that question isn't something I can help with. "
                "Let's keep things friendly! Ask me something else about the image.\""
            ),
            "messages": api_messages,
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
