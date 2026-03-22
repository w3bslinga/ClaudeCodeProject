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
    import yt_dlp
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    from googleapiclient.discovery import build as yt_build
    from youtube_transcript_api import YouTubeTranscriptApi
    import yt_dlp


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
        elif self.path.startswith("/debug-transcript?"):
            self._handle_debug_transcript()
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
        elif self.path == "/eli5":
            self._handle_eli5()
        elif self.path == "/prompt-engineer":
            self._handle_prompt_engineer()
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

    def _handle_debug_transcript(self):
        """Debug endpoint to see raw yt-dlp output."""
        from urllib.parse import urlparse, parse_qs
        query = parse_qs(urlparse(self.path).query)
        vid_id = query.get("v", [None])[0]
        if not vid_id:
            self._json_error(400, "Missing video ID")
            return
        try:
            url = f"https://www.youtube.com/watch?v={vid_id}"
            ydl_opts = {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["en", "en-US", "en-GB"],
                "subtitlesformat": "json3",
                "skip_download": True,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                subs = info.get("subtitles", {})
                auto_subs = info.get("automatic_captions", {})
                self._json_ok({
                    "title": info.get("title"),
                    "manual_sub_langs": list(subs.keys())[:10],
                    "auto_sub_langs": list(auto_subs.keys())[:10],
                    "has_manual_en": any(l.startswith("en") for l in subs.keys()),
                    "has_auto_en": any(l.startswith("en") for l in auto_subs.keys()),
                    "playability": info.get("playability_status"),
                })
        except Exception as e:
            self._json_ok({"error": f"{type(e).__name__}: {e}"})

    def _handle_transcript(self):
        """Proxy endpoint to fetch a YouTube video transcript using yt-dlp."""
        from urllib.parse import urlparse, parse_qs
        import tempfile

        query = parse_qs(urlparse(self.path).query)
        vid_id = query.get("v", [None])[0]
        if not vid_id:
            self._json_error(400, "Missing video ID")
            return

        # Method 1: yt-dlp (most reliable, handles bot detection)
        try:
            url = f"https://www.youtube.com/watch?v={vid_id}"
            ydl_opts = {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["en", "en-US", "en-GB"],
                "subtitlesformat": "json3",
                "skip_download": True,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Check for subtitles
                subs = info.get("subtitles", {})
                auto_subs = info.get("automatic_captions", {})

                # Prefer manual English subs, then auto-generated
                sub_data = None
                for lang in ["en", "en-US", "en-GB"]:
                    if lang in subs:
                        sub_data = subs[lang]
                        print(f"  📝 Found manual subs ({lang}) for {vid_id}")
                        break
                if not sub_data:
                    for lang in ["en", "en-US", "en-GB", "en-orig"]:
                        if lang in auto_subs:
                            sub_data = auto_subs[lang]
                            print(f"  📝 Found auto subs ({lang}) for {vid_id}")
                            break

                if not sub_data:
                    print(f"  ❌ No English subs for {vid_id}. Available: manual={list(subs.keys())[:5]}, auto={list(auto_subs.keys())[:5]}")
                    self._json_ok({"transcript": None})
                    return

                # Find json3 or vtt format URL
                sub_url = None
                for fmt in sub_data:
                    if fmt.get("ext") == "json3":
                        sub_url = fmt.get("url")
                        break
                if not sub_url:
                    for fmt in sub_data:
                        if fmt.get("ext") == "vtt":
                            sub_url = fmt.get("url")
                            break
                if not sub_url and sub_data:
                    sub_url = sub_data[0].get("url")

                if not sub_url:
                    self._json_ok({"transcript": None})
                    return

                # Fetch the subtitle content
                sub_req = urllib.request.Request(sub_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                })
                with urllib.request.urlopen(sub_req, timeout=15) as sr:
                    sub_content = sr.read().decode("utf-8", errors="replace")

                # Parse based on format
                text = ""
                try:
                    sub_json = json.loads(sub_content)
                    # json3 format
                    events = sub_json.get("events", [])
                    segments = []
                    for event in events:
                        segs = event.get("segs", [])
                        for seg in segs:
                            t = seg.get("utf8", "").strip()
                            if t and t != "\n":
                                segments.append(t)
                    text = " ".join(segments)
                except (json.JSONDecodeError, KeyError):
                    # VTT or other text format - extract text lines
                    import re
                    lines = sub_content.split("\n")
                    text_lines = []
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith("WEBVTT") or "-->" in line or re.match(r"^\d+$", line):
                            continue
                        # Remove VTT tags
                        clean = re.sub(r"<[^>]+>", "", line)
                        if clean.strip():
                            text_lines.append(clean.strip())
                    text = " ".join(text_lines)

                if text.strip():
                    print(f"  ✅ Transcript for {vid_id} via yt-dlp ({len(text)} chars)")
                    self._json_ok({"transcript": text[:15000]})
                    return
                else:
                    print(f"  ❌ Empty transcript for {vid_id}")

        except Exception as e:
            print(f"  ❌ yt-dlp failed for {vid_id}: {type(e).__name__}: {e}")

        # Method 2: Fallback to youtube-transcript-api
        try:
            yt_transcript = YouTubeTranscriptApi()
            result = yt_transcript.fetch(vid_id)
            text = " ".join(s.text for s in result.snippets)
            if text.strip():
                print(f"  ✅ Transcript for {vid_id} via youtube-transcript-api ({len(text)} chars)")
                self._json_ok({"transcript": text[:15000]})
                return
        except Exception as e:
            print(f"  ❌ youtube-transcript-api also failed for {vid_id}: {type(e).__name__}: {e}")

        self._json_ok({"transcript": None})

    def _handle_research(self):
        """Search YouTube, fetch transcripts (or descriptions as fallback), summarize with Claude."""
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
        direct_video_id = body.get("videoId", "").strip()
        max_results = min(body.get("maxVideos", 5), 5)
        fetch_count = min(max_results * 2, 8)

        if not topic and not direct_video_id:
            self._json_error(400, "No topic or videoId provided")
            return

        youtube = yt_build("youtube", "v3", developerKey=yt_key)

        # Direct YouTube link mode: skip search, use video ID directly
        if direct_video_id:
            print(f"  🔗 Direct video lookup: {direct_video_id}")
            video_ids = [direct_video_id]
            # Fetch video snippet to get title, channel, thumbnail
            try:
                vid_resp = youtube.videos().list(
                    part="snippet,contentDetails,statistics", id=direct_video_id
                ).execute()
                vid_items = vid_resp.get("items", [])
                if not vid_items:
                    self._json_ok({"results": []})
                    return
                d = vid_items[0]
                snippet = d["snippet"]
                videos = [{
                    "videoId": direct_video_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "link": f"https://www.youtube.com/watch?v={direct_video_id}",
                    "channel": snippet.get("channelTitle", ""),
                    "duration": self._parse_duration(d["contentDetails"]["duration"]),
                    "views": int(d.get("statistics", {}).get("viewCount", 0)),
                    "hasTranscript": False,
                    "bullets": [],
                }]
            except Exception as e:
                self._json_error(502, f"YouTube video lookup failed: {e}")
                return
        else:
            # 1. Search YouTube via Data API v3
            try:
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
                    "description": snippet.get("description", ""),
                    "thumbnail": snippet.get("thumbnails", {}).get("medium", {}).get("url", ""),
                    "link": f"https://www.youtube.com/watch?v={vid_id}",
                    "channel": snippet.get("channelTitle", ""),
                    "duration": "",
                    "views": 0,
                    "hasTranscript": False,
                    "bullets": [],
                })
                video_ids.append(vid_id)

            # 2. Fetch video durations, view counts, and FULL descriptions
            try:
                details_resp = youtube.videos().list(
                    part="contentDetails,statistics,snippet", id=",".join(video_ids)
                ).execute()
                duration_map = {}
                views_map = {}
                desc_map = {}
                for d in details_resp.get("items", []):
                    raw = d["contentDetails"]["duration"]
                    duration_map[d["id"]] = self._parse_duration(raw)
                    views_map[d["id"]] = int(d.get("statistics", {}).get("viewCount", 0))
                    desc_map[d["id"]] = d.get("snippet", {}).get("description", "")
                for v in videos:
                    v["duration"] = duration_map.get(v["videoId"], "")
                    v["views"] = views_map.get(v["videoId"], 0)
                    full_desc = desc_map.get(v["videoId"], "")
                    if full_desc:
                        v["description"] = full_desc
            except Exception:
                pass

        # 3. Try to fetch transcripts (works locally, may fail on datacenter IPs)
        transcripts = {}
        yt_transcript = YouTubeTranscriptApi()
        for vid_id in video_ids:
            # Try yt-dlp first
            try:
                url = f"https://www.youtube.com/watch?v={vid_id}"
                ydl_opts = {
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": ["en", "en-US", "en-GB"],
                    "subtitlesformat": "json3",
                    "skip_download": True,
                    "quiet": True,
                    "no_warnings": True,
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    subs = info.get("subtitles", {})
                    auto_subs = info.get("automatic_captions", {})
                    sub_data = None
                    for lang in ["en", "en-US", "en-GB"]:
                        if lang in subs:
                            sub_data = subs[lang]
                            break
                    if not sub_data:
                        for lang in ["en", "en-US", "en-GB", "en-orig"]:
                            if lang in auto_subs:
                                sub_data = auto_subs[lang]
                                break
                    if sub_data:
                        sub_url = None
                        for fmt in sub_data:
                            if fmt.get("ext") == "json3":
                                sub_url = fmt.get("url")
                                break
                        if not sub_url and sub_data:
                            sub_url = sub_data[0].get("url")
                        if sub_url:
                            sub_req = urllib.request.Request(sub_url, headers={
                                "User-Agent": "Mozilla/5.0",
                            })
                            with urllib.request.urlopen(sub_req, timeout=15) as sr:
                                sub_content = sr.read().decode("utf-8", errors="replace")
                            try:
                                sub_json = json.loads(sub_content)
                                segments = []
                                for event in sub_json.get("events", []):
                                    for seg in event.get("segs", []):
                                        t = seg.get("utf8", "").strip()
                                        if t and t != "\n":
                                            segments.append(t)
                                text = " ".join(segments)
                            except (json.JSONDecodeError, KeyError):
                                import re as _re
                                lines = sub_content.split("\n")
                                text_lines = [_re.sub(r"<[^>]+>", "", l.strip()) for l in lines
                                              if l.strip() and not l.startswith("WEBVTT") and "-->" not in l]
                                text = " ".join(text_lines)
                            if text.strip():
                                transcripts[vid_id] = text[:15000]
                                print(f"  ✅ Transcript for {vid_id} via yt-dlp ({len(text)} chars)")
                                continue
            except Exception as e:
                print(f"  ⚠️ yt-dlp failed for {vid_id}: {type(e).__name__}: {e}")

            # Try youtube-transcript-api
            try:
                result = yt_transcript.fetch(vid_id)
                text = " ".join(s.text for s in result.snippets)
                if text.strip():
                    transcripts[vid_id] = text[:15000]
                    print(f"  ✅ Transcript for {vid_id} via API ({len(text)} chars)")
                    continue
            except Exception as e:
                print(f"  ⚠️ transcript-api failed for {vid_id}: {type(e).__name__}: {e}")

        # Mark which have transcripts
        for v in videos:
            if v["videoId"] in transcripts:
                v["hasTranscript"] = True

        transcript_count = len(transcripts)
        print(f"  📊 {len(videos)} videos, {transcript_count} with transcripts")

        # Sort by views, take top results
        videos.sort(key=lambda v: v["views"], reverse=True)
        videos = videos[:max_results]

        # 4. Summarize with Claude - use transcripts where available, descriptions as fallback
        prompt_parts = []
        for v in videos:
            vid_id = v["videoId"]
            if vid_id in transcripts:
                source = f"Transcript:\n{transcripts[vid_id]}"
            else:
                desc = v.get("description", "")
                source = f"Video Description:\n{desc}" if desc else "No transcript or description available."
            prompt_parts.append(f'Video (id: {vid_id}): "{v["title"]}" by {v["channel"]}\n{source}')

        user_prompt = (
            "Summarize each of the following YouTube videos into 5-8 concise bullet points "
            "capturing the key insights and facts. Keep each bullet under 2 sentences. "
            "If only a description is provided (no transcript), do your best to summarize "
            "the likely content based on the title, channel, and description.\n\n"
            "Return ONLY a JSON array with objects like: "
            '[{"videoId": "...", "bullets": ["...", ...]}]\n\n'
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
                text_resp = result["content"][0]["text"].strip()
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
            print(f"  ⚠️ Summarization error: {type(e).__name__}: {e}")

        # Remove internal description field before sending to client
        for v in videos:
            v.pop("description", None)

        self._json_ok({"results": videos, "transcriptCount": transcript_count})

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

    def _handle_eli5(self):
        """Explain Like I'm 5 — initial explanation or follow-up chat."""
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

        topic = body.get("topic", "").strip()
        messages = body.get("messages", [])
        prompt = body.get("prompt", "").strip() or body.get("followUp", "").strip()

        # Initial request needs a topic; follow-ups need a prompt
        if not topic and not prompt:
            self._json_error(400, "No topic or prompt provided")
            return

        system_prompt = (
            "You are explaining complex topics to a 5-year-old child. "
            "Use simple words, fun analogies, and short sentences. Be enthusiastic and encouraging. "
            "Avoid jargon entirely. Use examples a child would understand like toys, animals, food, and games.\n\n"
            "If the user asks something inappropriate, offensive, or sexual, respond with: "
            "\"Oops! That's not something we can talk about. Let's pick a fun topic instead! "
            "How about asking me about dinosaurs, space, or rainbows?\"\n\n"
            "Keep explanations to 3-5 simple sentences. Make it fun and easy to understand."
        )

        # Build API messages, stripping trailing whitespace from assistant content
        api_messages = []
        if messages:
            for msg in messages:
                content = msg["content"].rstrip() if msg["role"] == "assistant" else msg["content"]
                api_messages.append({"role": msg["role"], "content": content})
            if prompt:
                api_messages.append({"role": "user", "content": prompt})
        else:
            api_messages.append({"role": "user", "content": f"Explain this topic: {topic}"})

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 1024,
            "system": system_prompt,
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

    def _handle_prompt_engineer(self):
        """Rewrite a rough prompt into an expert-level prompt, with optional refinement."""
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

        prompt = body.get("prompt", "").strip()
        engineered = body.get("engineered", "").strip()
        refinement = body.get("refinement", "").strip()

        if not prompt:
            self._json_error(400, "No prompt provided")
            return

        system_prompt = (
            "You are an expert prompt engineer. Your job is to take rough, vague, or poorly structured "
            "prompts and transform them into clear, effective, well-structured prompts that get the best "
            "results from AI language models.\n\n"
            "If the user's prompt is inappropriate, offensive, or sexual, respond with: "
            "\"I can't help engineer that kind of prompt. Please provide a constructive prompt "
            "that I can help improve.\"\n\n"
            "When rewriting, you should:\n"
            "- Add specificity and context where helpful\n"
            "- Include clear constraints and output format instructions\n"
            "- Add a persona or role if appropriate\n"
            "- Structure it logically with sections if needed\n"
            "- Keep it concise but comprehensive\n\n"
            "Return ONLY the improved prompt text. No explanations, no commentary, no markdown fences."
        )

        api_messages = []
        if refinement and engineered:
            # Refinement request
            api_messages.append({"role": "user", "content": f"Here is my rough prompt:\n\n{prompt}"})
            api_messages.append({"role": "assistant", "content": engineered})
            api_messages.append({"role": "user", "content": f"Please refine the engineered prompt with this instruction: {refinement}"})
        else:
            # Initial request
            api_messages.append({"role": "user", "content": f"Please engineer this prompt into a professional, effective prompt:\n\n{prompt}"})

        payload = {
            "model": CLAUDE_MODEL,
            "max_tokens": 2048,
            "system": system_prompt,
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
