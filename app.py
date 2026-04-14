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
        # 🔥 Call SnapInsta backend
        api_url = "https://snapinsta.app/action.php"

        response = requests.post(api_url, data={"url": url})

        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch video'}), 500

        html = response.text

        # 🔥 Extract video link
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
