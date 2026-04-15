from flask import Flask, request, jsonify, send_file, after_this_request
import yt_dlp
import os
import uuid
import time
from urllib.parse import urlparse

app = Flask(__name__)

@app.route('/')
def index():
    return send_file('index.html')


# ✅ NEW: robots.txt route (SEO)
@app.route('/robots.txt')
def robots():
    return "User-agent: *\nAllow: /\nSitemap: https://reelsnag.site/sitemap.xml", 200, {'Content-Type': 'text/plain'}


@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()

    # 🔒 Rate limit (simple)
    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not hasattr(app, "ip_store"):
        app.ip_store = {}

    now = time.time()
    window = 60
    limit = 5

    if user_ip not in app.ip_store:
        app.ip_store[user_ip] = []

    app.ip_store[user_ip] = [t for t in app.ip_store[user_ip] if now - t < window]

    if len(app.ip_store[user_ip]) >= limit:
        return jsonify({'error': 'Too many requests. Try again in a minute.'}), 429

    app.ip_store[user_ip].append(now)

    # 🔒 Validate URL
    if not url:
        return jsonify({'error': 'Please provide a URL.'}), 400

    try:
        parsed = urlparse(url)
        if "instagram.com" not in parsed.netloc or ("/reel/" not in parsed.path and "/p/" not in parsed.path):
            return jsonify({'error': 'Enter a valid Instagram reel link.'}), 400
    except:
        return jsonify({'error': 'Invalid URL format.'}), 400

    try:
        tmp_path = f"/tmp/{uuid.uuid4()}"

        ydl_opts = {
            'outtmpl': tmp_path + '.%(ext)s',
            'format': 'best',
            'quiet': True,
            'no_warnings': True,

            # 🔥 Prevent blocking
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            },

            # 🔥 Timeout protection
            'socket_timeout': 10
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            # keep your original fix
            if not file_path.endswith('.mp4'):
                file_path = os.path.splitext(file_path)[0] + '.mp4'

        if not os.path.exists(file_path):
            return jsonify({'error': 'Download failed'}), 500

        # ✅ SAFE CLEANUP
        @after_this_request
        def cleanup(response):
            try:
                os.remove(file_path)
            except Exception as e:
                print("Cleanup error:", e)
            return response

        return send_file(
            file_path,
            as_attachment=True,
            download_name='reel.mp4',
            mimetype='video/mp4'
        )

    except Exception as e:
        print("ERROR:", str(e))
        msg = str(e).lower()

        if "private" in msg:
            return jsonify({'error': 'Private reels are not supported.'}), 400
        elif "timeout" in msg:
            return jsonify({'error': 'Request timed out. Try again.'}), 500
        else:
            return jsonify({'error': 'Failed to download. Try another reel.'}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
