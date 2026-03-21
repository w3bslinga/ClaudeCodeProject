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

    def do_POST(self):
        if self.path == "/analyze":
            self._handle_analyze()
        elif self.path == "/chat":
            self._handle_chat()
        elif self.path == "/research":
            self._handle_research()
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

    def _handle_research(self):
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

        yt_key = os.environ.get("YOUTUBE_API_KEY", "")
        if not yt_key:
            self._json_error(401, "YOUTUBE_API_KEY is not set.")
            return

        topic = body.get("topic", "").strip()
        max_results = min(body.get("maxVideos", 5), 5)
        # Fetch more to compensate for videos without transcripts
        fetch_count = min(max_results * 2, 8)

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
        if not items:
            self._json_ok({"results": []})
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
                "hasTranscript": False,
                "bullets": [],
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
                raw = d["contentDetails"]["duration"]  # e.g. PT12M34S
                duration_map[d["id"]] = self._parse_duration(raw)
                views_map[d["id"]] = int(d.get("statistics", {}).get("viewCount", 0))
            for v in videos:
                v["duration"] = duration_map.get(v["videoId"], "")
                v["views"] = views_map.get(v["videoId"], 0)
        except Exception:
            pass  # durations/views are optional

        # 3. Fetch transcripts
        transcripts = {}  # videoId -> text
        yt_transcript = YouTubeTranscriptApi()
        for vid_id in video_ids:
            try:
                result = yt_transcript.fetch(vid_id)
                text = " ".join(s.text for s in result.snippets)
                # Truncate to ~15k chars
                transcripts[vid_id] = text[:15000]
            except Exception:
                pass  # no transcript available

        # Mark which have transcripts
        for v in videos:
            if v["videoId"] in transcripts:
                v["hasTranscript"] = True

        # 4. Summarize with Claude (single batch call)
        if transcripts:
            prompt_parts = []
            for vid_id, text in transcripts.items():
                title = next((v["title"] for v in videos if v["videoId"] == vid_id), "")
                prompt_parts.append(f'Video (id: {vid_id}): "{title}"\nTranscript:\n{text}')

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
                    # Strip markdown fences if present
                    text_resp = text_resp.strip()
                    if text_resp.startswith("```"):
                        text_resp = text_resp.split("\n", 1)[1]
                        if text_resp.endswith("```"):
                            text_resp = text_resp[:-3]
                    summaries = json.loads(text_resp.strip())
                    summary_map = {s["videoId"]: s["bullets"] for s in summaries}
                    for v in videos:
                        if v["videoId"] in summary_map:
                            v["bullets"] = summary_map[v["videoId"]]
            except urllib.error.HTTPError as e:
                err_body = e.read().decode()
                print(f"  ⚠️ Summarization HTTP error {e.code}: {err_body[:500]}")
            except Exception as e:
                # If summarization fails, still return videos without bullets
                print(f"  ⚠️ Summarization error: {type(e).__name__}: {e}")

        # Filter to only videos with transcripts, sort by views descending, cap at max_results
        videos = [v for v in videos if v["hasTranscript"]]
        videos.sort(key=lambda v: v["views"], reverse=True)
        videos = videos[:max_results]

        self._json_ok({"results": videos})

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
