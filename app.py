

from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import uuid
import re

app = Flask(__name__)

INSTAGRAM_PATTERN = re.compile(r'instagram.com/(reel|p|tv)/[A-Za-z0-9_-]+')

def is_valid_instagram_url(url):
    return bool(INSTAGRAM_PATTERN.search(url))

@app.route('/')
def index():
    with open('index.html', 'r') as f:
        return f.read()

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Please provide a URL.'}), 400

    if not is_valid_instagram_url(url):
        return jsonify({'error': 'That does not look like an Instagram Reel URL.'}), 400

    tmp_path = f"/tmp/{uuid.uuid4()}"
    output_file = f"{tmp_path}.mp4"

    ydl_opts = {
        'outtmpl': tmp_path + '.%(ext)s',
        'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded = ydl.prepare_filename(info)

            if not downloaded.endswith('.mp4'):
                base = os.path.splitext(downloaded)[0]
                downloaded = base + '.mp4'

        if not os.path.exists(downloaded):
            return jsonify({'error': 'Download failed. The reel may be private or deleted.'}), 500

        return send_file(
            downloaded,
            as_attachment=True,
            download_name='reel.mp4',
            mimetype='video/mp4'
        )

    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if 'login' in msg.lower() or 'private' in msg.lower():
            return jsonify({'error': 'This reel is private or requires login.'}), 403
        return jsonify({'error': 'Could not download. Try a different reel URL.'}), 500

    except Exception as e:
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500


# 🔥 IMPORTANT FOR RENDER
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
