#!/usr/bin/env python3
"""
image-analyzer server
Serves static files + proxies Claude API calls to avoid CORS.
Usage: ANTHROPIC_API_KEY=sk-... python3 server.py
"""

import http.server
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

# Auto-install dependencies if missing (needed for Render deployment)
try:
    from googleapiclient.discovery import build as yt_build
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    from googleapiclient.discovery import build as yt_build
    from youtube_transcript_api import YouTubeTranscriptApi


def load_dotenv(path=".env"):
    """Load key=value pairs from a .env file into os.environ."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    k, v = key.strip(), val.strip().strip("\"'")
                    if v:  # only set if value is non-empty
                        os.environ[k] = v
    except FileNotFoundError:
        pass

PORT = int(os.environ.get("PORT", 8788))
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-opus-4-6"


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} — {fmt % args}")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        # Handle transcript proxy endpoint
        if self.path.startswith("/transcript?"):
            self._handle_transcript()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/analyze":
            self._handle_analyze()
        elif self.path == "/chat":
            self._handle_chat()
        elif self.path == "/research":
            self._handle_research()
        elif self.path == "/summarize":
            self._handle_summarize()
        elif self.path == "/super-summary":
            self._handle_super_summary()
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

    def _handle_transcript(self):
        """Proxy endpoint to fetch a YouTube video transcript."""
        from urllib.parse import urlparse, parse_qs
        import xml.etree.ElementTree as ET

        query = parse_qs(urlparse(self.path).query)
        vid_id = query.get("v", [None])[0]
        if not vid_id:
            self._json_error(400, "Missing video ID")
            return

        # Method 1: youtube-transcript-api
        try:
            yt_transcript = YouTubeTranscriptApi()
            result = yt_transcript.fetch(vid_id)
            text = " ".join(s.text for s in result.snippets)
            if text.strip():
                print(f"  ✅ Transcript for {vid_id} via API ({len(text)} chars)")
                self._json_ok({"transcript": text[:15000]})
                return
        except Exception as e:
            print(f"  ⚠️ API transcript failed for {vid_id}: {type(e).__name__}: {e}")

        # Method 2: YouTube Innertube API with Android client (fewer restrictions)
        for client_config in [
            {
                "clientName": "ANDROID",
                "clientVersion": "19.09.37",
                "androidSdkVersion": 30,
                "userAgent": "com.google.android.youtube/19.09.37 (Linux; U; Android 11) gzip",
                "platform": "MOBILE",
            },
            {
                "clientName": "WEB",
                "clientVersion": "2.20240101.00.00",
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        ]:
            try:
                client_name = client_config["clientName"]
                user_agent = client_config.pop("userAgent", "")
                platform = client_config.pop("platform", None)

                context = {"client": {**client_config}}
                if platform:
                    context["client"]["platform"] = platform

                innertube_payload = json.dumps({
                    "context": context,
                    "videoId": vid_id,
                    "contentCheckOk": True,
                    "racyCheckOk": True,
                }).encode()

                innertube_req = urllib.request.Request(
                    "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
                    data=innertube_payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": user_agent,
                        "Cookie": "SOCS=CAESEwgDEgk2NjI1Njc1NjQaAmVuIAEaBgiA_ZOYBA",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(innertube_req, timeout=15) as resp:
                    player_data = json.loads(resp.read())

                playability = player_data.get("playabilityStatus", {}).get("status", "")
                captions = player_data.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
                tracks = captions.get("captionTracks", [])
                print(f"  📡 Innertube {client_name} for {vid_id}: playability={playability}, tracks={len(tracks)}")

                if not tracks:
                    continue

                # Prefer English, fallback to first track
                cap_url = tracks[0].get("baseUrl", "")
                for t in tracks:
                    if t.get("languageCode", "").startswith("en"):
                        cap_url = t.get("baseUrl", "")
                        break

                if not cap_url:
                    continue

                # Fetch the caption XML
                cap_req = urllib.request.Request(cap_url, headers={
                    "User-Agent": user_agent or "Mozilla/5.0",
                })
                with urllib.request.urlopen(cap_req, timeout=10) as cr:
                    cap_xml = cr.read().decode("utf-8", errors="replace")

                root = ET.fromstring(cap_xml)
                texts = [elem.text for elem in root.findall(".//text") if elem.text]
                text = " ".join(texts)
                if text.strip():
                    print(f"  ✅ Transcript for {vid_id} via {client_name} ({len(text)} chars)")
                    self._json_ok({"transcript": text[:15000]})
                    return
                else:
                    print(f"  ❌ Empty transcript for {vid_id} via {client_name}")
            except Exception as e2:
                print(f"  ❌ Innertube {client_config.get('clientName','?')} failed for {vid_id}: {type(e2).__name__}: {e2}")

        self._json_ok({"transcript": None})

    def _handle_research(self):
        """Step 1: Search YouTube, return video metadata (no transcripts - done client-side)."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
        except Exception:
            self._json_error(400, "Invalid request body")
            return

        yt_key = os.environ.get("YOUTUBE_API_KEY", "")
        if not yt_key:
            self._json_error(401, "YOUTUBE_API_KEY is not set.")
            return

        topic = body.get("topic", "").strip()
        fetch_count = min(body.get("maxVideos", 8), 8)

        if not topic:
            self._json_error(400, "No topic provided")
            return

        # 1. Search YouTube via Data API v3
        try:
            youtube = yt_build("youtube", "v3", developerKey=yt_key)
            search_resp = youtube.search().list(
                q=topic, part="snippet", type="video",
                maxResults=fetch_count, relevanceLanguage="en"
            ).execute()
        except Exception as e:
            self._json_error(502, f"YouTube search failed: {e}")
            return

        items = search_resp.get("items", [])
        print(f"  🔍 YouTube search for '{topic}': {len(items)} results")
        if not items:
            self._json_ok({"videos": []})
            return

        # Extract video metadata
        videos = []
        video_ids = []
        for item in items:
            vid_id = item["id"]["videoId"]
            snippet = item["snippet"]
            videos.append({
                "videoId": vid_id,
                "title": snippet.get("title", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                "link": f"https://www.youtube.com/watch?v={vid_id}",
                "channel": snippet.get("channelTitle", ""),
                "duration": "",
                "views": 0,
            })
            video_ids.append(vid_id)

        # 2. Fetch video durations and view counts
        try:
            details_resp = youtube.videos().list(
                part="contentDetails,statistics", id=",".join(video_ids)
            ).execute()
            duration_map = {}
            views_map = {}
            for d in details_resp.get("items", []):
                raw = d["contentDetails"]["duration"]
                duration_map[d["id"]] = self._parse_duration(raw)
                views_map[d["id"]] = int(d.get("statistics", {}).get("viewCount", 0))
            for v in videos:
                v["duration"] = duration_map.get(v["videoId"], "")
                v["views"] = views_map.get(v["videoId"], 0)
        except Exception:
            pass

        self._json_ok({"videos": videos})

    def _handle_summarize(self):
        """Step 2: Receive transcripts from client, summarize with Claude."""
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

        # Expect: { "videos": [{ "videoId", "title", "transcript" }, ...] }
        video_data = body.get("videos", [])
        if not video_data:
            self._json_error(400, "No video transcripts provided")
            return

        prompt_parts = []
        for vd in video_data:
            transcript = vd.get("transcript", "")[:15000]
            prompt_parts.append(f'Video (id: {vd["videoId"]}): "{vd.get("title", "")}"\nTranscript:\n{transcript}')

        user_prompt = (
            "Summarize each of the following YouTube video transcripts into 5-8 concise bullet points "
            "capturing the key insights and facts. Keep each bullet under 2 sentences.\n\n"
            "Return ONLY a JSON array with objects like: "
            '[{"videoId": "...", "bullets": ["...", ...]}}]\n\n'
            + "\n\n---\n\n".join(prompt_parts)
        )

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 4096,
            "system": "You are a research assistant. Return only valid JSON, no markdown fences.",
            "messages": [{"role": "user", "content": user_prompt}],
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
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                text_resp = result["content"][0]["text"]
                text_resp = text_resp.strip()
                if text_resp.startswith("```"):
                    text_resp = text_resp.split("\n", 1)[1]
                    if text_resp.endswith("```"):
                        text_resp = text_resp[:-3]
                summaries = json.loads(text_resp.strip())
                self._json_ok({"summaries": summaries})
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"  ⚠️ Summarization HTTP error {e.code}: {err_body[:500]}")
            self._json_error(e.code, f"Claude API error: {err_body[:200]}")
        except Exception as e:
            print(f"  ⚠️ Summarization error: {type(e).__name__}: {e}")
            self._json_error(500, str(e))

    def _handle_super_summary(self):
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

        topic = body.get("topic", "")
        results = body.get("results", [])

        if not results:
            self._json_error(400, "No results provided")
            return

        # Build a prompt from all the per-video bullet summaries
        video_summaries = []
        for r in results:
            if r.get("bullets"):
                bullets_text = "\n".join(f"- {b}" for b in r["bullets"])
                video_summaries.append(f'Video: "{r.get("title", "")}" ({r.get("channel", "")})\n{bullets_text}')

        if not video_summaries:
            self._json_error(400, "No summaries to consolidate")
            return

        user_prompt = (
            f'The user researched "{topic}" and found the following YouTube video summaries:\n\n'
            + "\n\n---\n\n".join(video_summaries)
            + "\n\n---\n\n"
            "Create a consolidated Super Summary that synthesizes the key insights across ALL videos into "
            "a single cohesive overview. Structure it as:\n"
            "1. A brief 2-3 sentence overview paragraph\n"
            "2. 5-10 key takeaways as bullet points, combining and deduplicating insights from all videos\n"
            "3. A brief conclusion sentence\n\n"
            "Return plain text, not JSON. Use bullet points with dashes (-)."
        )

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 2048,
            "system": "You are a research assistant creating a consolidated summary from multiple video summaries.",
            "messages": [{"role": "user", "content": user_prompt}],
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
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                text = result["content"][0]["text"]
                self._json_ok({"summary": text})
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

    @staticmethod
    def _parse_duration(iso):
        """Convert ISO 8601 duration (PT1H2M3S) to human-readable string."""
        import re
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
        if not m:
            return ""
        h, mi, s = m.group(1), m.group(2), m.group(3)
        h = int(h) if h else 0
        mi = int(mi) if mi else 0
        s = int(s) if s else 0
        if h:
            return f"{h}:{mi:02d}:{s:02d}"
        return f"{mi}:{s:02d}"

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
    print(f"\n  🔍 API server → http://localhost:{PORT}")
    key_set = bool(os.environ.get("ANTHROPIC_API_KEY"))
    yt_key_set = bool(os.environ.get("YOUTUBE_API_KEY"))
    if not key_set:
        print("  ⚠️  ANTHROPIC_API_KEY is not set!")
        print("  ➜  Restart with: ANTHROPIC_API_KEY=sk-ant-... python3 server.py\n")
    else:
        print("  🔑 Anthropic API key: ✅ ready")
    if not yt_key_set:
        print("  ⚠️  YOUTUBE_API_KEY is not set (Research Center won't work)")
    else:
        print("  🔑 YouTube API key: ✅ ready")
    print()
    server = http.server.HTTPServer(("", PORT), Handler)
    server.serve_forever()
