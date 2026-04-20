from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import time
import threading
import json
from urllib.parse import urlparse

app = Flask(__name__)

@app.after_request
def add_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return response


# 🔥 SEO CONFIG (SAFE ADD)
SEO_PAGES = {
    "download-instagram-reels": {
        "title": "Download Instagram Reels Free HD | ReelSnag",
        "heading": "Download Instagram Reels",
        "subtitle": "Free HD reel downloader online",
        "content": "Download Instagram reels free in HD with no watermark using ReelSnag."
    },
    "reels-downloader": {
        "title": "Best Reels Downloader Online | ReelSnag",
        "heading": "Reels Downloader",
        "subtitle": "Fast and free reel downloader",
        "content": "Best reels downloader to save Instagram videos instantly without watermark."
    },
    "download-instagram-reels-india": {
        "title": "Download Instagram Reels India | ReelSnag",
        "heading": "Download Instagram Reels India",
        "subtitle": "Fast for Jio & Airtel users",
        "content": "Download Instagram reels in India without watermark. Fast and free tool."
    }
}


# 🔥 SAFE SEO INJECTION (NO TEMPLATE ENGINE)
def inject_seo(html, seo):
    seo_script = f"""
<script>
window.SERVER_SEO = {json.dumps(seo)};
</script>
"""
    return html.replace("</head>", seo_script + "\n</head>")


# 🔥 ROOT (MODIFIED ONLY INTERNALLY)
@app.route('/')
def index():
    seo = {
        "title": "Download Instagram Reels Without Watermark (Free) | ReelSnag",
        "heading": "Download Instagram Reels",
        "subtitle": "Paste your reel link and download instantly",
        "content": "ReelSnag is a free Instagram reel downloader that allows users to download reels without watermark in HD quality."
    }

    with open("index.html", "r") as f:
        html = f.read()

    return inject_seo(html, seo)


# 🔥 PROGRAMMATIC SEO ROUTE (NEW)
@app.route('/<slug>')
def seo_page(slug):
    seo = SEO_PAGES.get(slug)

    if not seo:
        seo = {
            "title": f"{slug.replace('-', ' ').title()} | ReelSnag",
            "heading": slug.replace('-', ' ').title(),
            "subtitle": "Download Instagram reels instantly",
            "content": f"Use ReelSnag to {slug.replace('-', ' ')} without watermark in HD."
        }

    with open("index.html", "r") as f:
        html = f.read()

    return inject_seo(html, seo)


# 🔥 EXISTING CLEANUP (UNCHANGED)
def delete_file_later(path):
    time.sleep(2)
    try:
        if os.path.exists(path):
            os.remove(path)
    except:
        pass


# 🔥 TRACK (SAFE KEEP)
@app.route('/track', methods=['POST'])
def track():
    return jsonify({"status": "ok"})


# 🔥 DOWNLOAD (100% UNTOUCHED)
@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json(force=True)
        url = data.get('url', '').strip()
    except:
        return jsonify({'error': 'Invalid request'}), 400

    if not url:
        return jsonify({'error': 'Please provide a URL.'}), 400

    try:
        parsed = urlparse(url)
        if "instagram.com" not in parsed.netloc:
            return jsonify({'error': 'Invalid Instagram URL'}), 400
    except:
        return jsonify({'error': 'Invalid URL format'}), 400

    try:
        tmp_path = f"/tmp/{uuid.uuid4()}"

        ydl_opts = {
            'outtmpl': tmp_path + '.%(ext)s',
            'format': 'best',
            'quiet': True,
            'no_warnings': True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            if not file_path.endswith('.mp4'):
                file_path = os.path.splitext(file_path)[0] + '.mp4'

        if not os.path.exists(file_path):
            return jsonify({'error': 'Download failed'}), 500

        threading.Thread(target=delete_file_later, args=(file_path,)).start()

        return send_file(
            file_path,
            as_attachment=True,
            download_name='reel.mp4',
            mimetype='video/mp4'
        )

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({'error': 'Failed to download'}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
