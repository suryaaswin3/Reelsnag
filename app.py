from flask import Flask, request, jsonify, send_file
import requests
import io
import re

app = Flask(__name__)

@app.route('/')
def index():
    return send_file('index.html')


def clean_url(url):
    # Remove query params like ?igsh=...
    return url.split("?")[0]


@app.route('/download', methods=['POST'])
def download():
    data = request.get_json()
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'Please provide a URL.'}), 400

    try:
        url = clean_url(url)

        # 🔥 Convert to JSON endpoint
        if "/reel/" in url:
            shortcode = url.split("/reel/")[1].split("/")[0]
        elif "/p/" in url:
            shortcode = url.split("/p/")[1].split("/")[0]
        else:
            return jsonify({'error': 'Invalid Instagram URL'}), 400

        api_url = f"https://www.instagram.com/p/{shortcode}/?__a=1&__d=dis"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        res = requests.get(api_url, headers=headers)

        if res.status_code != 200:
            return jsonify({'error': 'Failed to fetch data'}), 500

        data = res.json()

        # 🔥 Extract video URL
        video_url = None

        try:
            video_url = data["items"][0]["video_versions"][0]["url"]
        except:
            try:
                video_url = data["graphql"]["shortcode_media"]["video_url"]
            except:
                return jsonify({'error': 'Video not found'}), 500

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
