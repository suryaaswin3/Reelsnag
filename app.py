from flask import Flask, request, jsonify, send_file
from flask_compress import Compress
import yt_dlp
import os
import uuid
import time
import threading
import logging
import shutil
import subprocess
from urllib.parse import urlparse
from datetime import datetime
from threading import Lock

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
Compress(app)

# ---------------- TEMP DIR ----------------
TMP_DIR = "/tmp/reelsnag" if os.name != 'nt' else os.path.join(os.environ.get('TEMP', '.'), 'reelsnag')

# Clean temp on start
if os.path.exists(TMP_DIR):
    for f in os.listdir(TMP_DIR):
        try:
            os.remove(os.path.join(TMP_DIR, f))
        except:
            pass

# ---------------- UTILS ----------------
class YTDLPLogger:
    def debug(self, msg): logger.info(f"[yt-dlp] {msg}")
    def info(self, msg): logger.info(f"[yt-dlp] {msg}")
    def warning(self, msg): logger.warning(f"[yt-dlp] {msg}")
    def error(self, msg): logger.error(f"[yt-dlp] {msg}")


def is_valid_instagram_url(url: str) -> bool:
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower()

        if host.startswith("www."):
            host = host[4:]

        valid_hosts = {"instagram.com", "m.instagram.com", "l.instagram.com"}
        if host not in valid_hosts:
            return False

        path = p.path or ""
        return any(x in path for x in ["/reel/", "/reels/", "/p/", "/tv/"])
    except:
        return False


def has_video_stream(file_path: str) -> bool:
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        raise RuntimeError("ffprobe not installed")

    cmd = [
        ffprobe_path,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "json",
        file_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

    if result.returncode != 0:
        logger.error(f"ffprobe failed: {result.stderr}")
        return False

    try:
        import json
        parsed = json.loads(result.stdout or "{}")
        return bool(parsed.get("streams"))
    except:
        return False


# ---------------- RATE LIMIT (THREAD SAFE) ----------------
rate_limit_store = {}
rate_limit_lock = Lock()
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 10

def check_rate_limit(ip):
    with rate_limit_lock:
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

from flask import send_from_directory

@app.route("/")
def home():
    return send_from_directory(".", "index.html")
    
 @app.route('/stats')
def stats():
    return "Stats working"

@app.route('/track', methods=['GET', 'POST'])
def track():
    if request.method == 'POST':
        data = request.json
        print("Tracking:", data)
        return {"status": "ok"}
    return "Track endpoint working"   

@app.route("/<path:slug>")
def seo_pages(slug):
    return send_from_directory(".", "index.html")
# ---------------- DOWNLOAD ----------------
@app.route('/download', methods=['POST'])
def download():
    ip = request.remote_addr or "unknown"

    if not check_rate_limit(ip):
        return jsonify({"error": "Too many requests"}), 429

    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()

        if not url or not is_valid_instagram_url(url):
            return jsonify({"error": "Invalid Instagram URL"}), 400

        if not shutil.which("ffmpeg"):
            return jsonify({"error": "Server misconfigured: ffmpeg not installed"}), 500

        if not shutil.which("ffprobe"):
            return jsonify({"error": "Server misconfigured: ffprobe not installed"}), 500

        os.makedirs(TMP_DIR, exist_ok=True)

        file_id = str(uuid.uuid4())
        path = os.path.join(TMP_DIR, file_id)

        ydl_opts = {
            'outtmpl': path + '.%(ext)s',
            'quiet': False,
            'no_warnings': False,
            'verbose': True,
            'logger': YTDLPLogger(),
            'format': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b',
            'merge_output_format': 'mp4',
            'prefer_ffmpeg': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,

            # 🔥 COOKIES + HEADERS (BIG FIX)
            'cookiefile': 'cookies.txt',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.instagram.com/',
                'Origin': 'https://www.instagram.com'
            }
        }

        last_error = None

        for attempt in range(1, 4):
            try:
                time.sleep(1.5 * attempt)  # smart delay
                logger.info(f"Attempt {attempt}")

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(url, download=True)

                last_error = None
                break

            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt} failed: {last_error}")

        if last_error:
            err = last_error.lower()

            if "login" in err or "private" in err:
                return jsonify({"error": "Private reel or login required"}), 400
            elif "unsupported" in err:
                return jsonify({"error": "Invalid Instagram URL"}), 400
            elif "timeout" in err:
                return jsonify({"error": "Instagram timeout, try again"}), 500
            elif "network" in err:
                return jsonify({"error": "Network error, retry"}), 500
            else:
                return jsonify({"error": "Failed to fetch video stream"}), 500

        file_path = None
        for f in os.listdir(TMP_DIR):
            if f.startswith(file_id) and f.endswith(".mp4"):
                file_path = os.path.join(TMP_DIR, f)
                break

        if not file_path or not os.path.exists(file_path) or os.path.getsize(file_path) < 50000:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"error": "Invalid video"}), 500

        try:
            if not has_video_stream(file_path):
                os.remove(file_path)
                return jsonify({"error": "No video stream"}), 500
        except RuntimeError:
            return jsonify({"error": "Server misconfigured: ffprobe not installed"}), 500

        def cleanup():
            time.sleep(120)
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass

        threading.Thread(target=cleanup, daemon=True).start()

        return send_file(
            file_path,
            as_attachment=True,
            download_name="video.mp4",
            mimetype="video/mp4"
        )

    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({"error": "Server error"}), 500


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, threaded=True)
