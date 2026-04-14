from flask import Flask, request, jsonify, send_file
import requests
import re
import io

app = Flask(__name__)

@app.route('/')
def index():
    return send_file('index.html')


@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Please provide a URL.'}), 400

    try:
        # 🔥 SnapInsta request (with headers to avoid blocking)
        api_url = "https://snapinsta.app/action.php"

        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://snapinsta.app",
            "Referer": "https://snapinsta.app/"
        }

        response = requests.post(api_url, data={"url": url}, headers=headers)

        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch video'}), 500

        html = response.text

        # 🔥 Extract video links
        video_urls = re.findall(r'https?://[^"\']+\.mp4', html)

        if not video_urls:
            return jsonify({'error': 'Could not extract video'}), 500

        video_url = video_urls[0]

        # 🔥 Download video
        video = requests.get(video_url)

        return send_file(
            io.BytesIO(video.content),
            mimetype='video/mp4',
            as_attachment=True,
            download_name='reel.mp4'
        )

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
