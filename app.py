from flask import Flask, request, jsonify, send_file, after_this_request, make_response
import yt_dlp
import os
import uuid
import time
from urllib.parse import urlparse

app = Flask(__name__)

@app.after_request
def add_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return response


@app.route('/')
def index():
    return send_file('index.html')


@app.route('/download', methods=['GET'])
def download():
    url = request.args.get('url', '').strip()

    if not url:
        return "Invalid URL", 400

    try:
        parsed = urlparse(url)
        if "instagram.com" not in parsed.netloc:
            return "Invalid Instagram URL", 400
    except:
        return "Invalid URL", 400

    try:
        tmp_path = f"/tmp/{uuid.uuid4()}"

        ydl_opts = {
            'outtmpl': tmp_path + '.%(ext)s',
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0'
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            if not file_path.endswith('.mp4'):
                file_path = os.path.splitext(file_path)[0] + '.mp4'

        if not os.path.exists(file_path):
            return "Download failed", 500

        @after_this_request
        def cleanup(response):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
            return response

        # 🔥 UNIQUE NAME + HEADERS
        response = make_response(send_file(
            file_path,
            as_attachment=True,
            download_name=f"reelsnag_{uuid.uuid4().hex}.mp4",
            mimetype='video/mp4'
        ))

        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    except Exception as e:
        print("ERROR:", str(e))
        return "Download failed", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
