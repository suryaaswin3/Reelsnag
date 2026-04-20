from flask import Flask, request, jsonify, send_file, Response, make_response
import yt_dlp
import os
import uuid
import time
import threading
import json
import logging
from urllib.parse import urlparse
from functools import lru_cache
from datetime import datetime, timedelta

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------- RATE LIMIT ----------------
rate_limit_store = {}
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 10

def check_rate_limit(ip):
    now = datetime.now()
    data = rate_limit_store.get(ip)

    if not data:
        rate_limit_store[ip] = {'count': 1, 'start': now}
        return True

    if (now - data['start']).seconds > RATE_LIMIT_WINDOW:
        rate_limit_store[ip] = {'count': 1, 'start': now}
        return True

    if data['count'] >= RATE_LIMIT_MAX:
        return False

    data['count'] += 1
    return True

# ---------------- SECURITY HEADERS ----------------
@app.after_request
def headers(res):
    res.headers['X-Content-Type-Options'] = 'nosniff'
    res.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return res

# ---------------- SEO DATA ----------------
SEO_PAGES = {
    "download-instagram-reels": {
        "title": "Download Instagram Reels Free HD | ReelSnag",
        "description": "Download Instagram reels free in HD with no watermark.",
        "heading": "Download Instagram Reels",
        "subtitle": "Free HD reel downloader",
        "content": "Download Instagram reels in HD without watermark."
    },
    "reels-downloader": {
        "title": "Best Reels Downloader | ReelSnag",
        "description": "Fast reels downloader online.",
        "heading": "Reels Downloader",
        "subtitle": "Fast and free",
        "content": "Best reels downloader tool."
    }
}

# ---------------- SEO INJECTION ----------------
@lru_cache(maxsize=50)
def inject_seo_cached(html, slug):
    try:
        seo = SEO_PAGES.get(slug)

        if not seo:
            seo = {
                "title": slug.replace('-', ' ').title() + " | ReelSnag",
                "description": "Download Instagram reels easily.",
                "heading": slug.replace('-', ' ').title(),
                "subtitle": "Download reels instantly",
                "content": "Free reel downloader"
            }

        canonical = "https://reelsnag.site/" if slug == "" else f"https://reelsnag.site/{slug}"

        # Inject script
        script = f'<script>window.SERVER_SEO={json.dumps(seo)}</script>'
        html = html.replace("</head>", script + "</head>")

        # Replace title
        html = html.replace(
            "<title>Download Instagram Reels Without Watermark (Free) | ReelSnag</title>",
            f"<title>{seo['title']}</title>"
        )

        # Replace canonical
        html = html.replace(
            '<link rel="canonical" href="https://reelsnag.site/" />',
            f'<link rel="canonical" href="{canonical}" />'
        )

        return html

    except Exception as e:
        print("SEO ERROR:", e)
        return html

# ---------------- ROUTES ----------------

@app.route('/')
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    return inject_seo_cached(html, "")

@app.route('/<slug>')
def seo_page(slug):
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
        return make_response(inject_seo_cached(html, slug))
    except Exception as e:
        print("SEO PAGE ERROR:", e)
        return "Error", 500

# ---------------- TRACK ----------------
@app.route('/track', methods=['POST'])
def track():
    try:
        data = request.get_json(force=True)
        logger.info(f"TRACK: {data}")
        return jsonify({"ok": True})
    except:
        return jsonify({"ok": True})

# ---------------- DOWNLOAD ----------------
@app.route('/download', methods=['POST'])
def download():
    ip = request.remote_addr or "unknown"

    if not check_rate_limit(ip):
        return jsonify({"error": "Too many requests"}), 429

    try:
        url = request.json.get("url", "").strip()
        if "instagram.com" not in url:
            return jsonify({"error": "Invalid URL"}), 400

        tmp_dir = "/tmp/reelsnag"
        os.makedirs(tmp_dir, exist_ok=True)
        path = os.path.join(tmp_dir, str(uuid.uuid4()))

        ydl_opts = {'outtmpl': path + '.%(ext)s', 'quiet': True}

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        if not file_path.endswith(".mp4"):
            new = file_path.split(".")[0] + ".mp4"
            os.rename(file_path, new)
            file_path = new

        threading.Thread(target=lambda: (time.sleep(5), os.remove(file_path)), daemon=True).start()

        res = send_file(file_path, as_attachment=True, download_name="reel.mp4")
        res.headers['X-Site-URL'] = request.host_url.rstrip('/')
        return res

    except Exception as e:
        print("DOWNLOAD ERROR:", e)
        return jsonify({"error": "Download failed"}), 500

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
