from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import time
import threading
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


# 🔥 NEW: delayed cleanup
def delete_file_later(path):
    time.sleep(2)  # small delay fixes your bug
    try:
        if os.path.exists(path):
            os.remove(path)
    except:
        pass


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

        # 🔥 FIX: delayed deletion instead of immediate
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
