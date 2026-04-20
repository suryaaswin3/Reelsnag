from flask import Flask, request, jsonify, send_file, make_response, after_this_request
from flask import Response
from flask_compress import Compress
import yt_dlp
import os
import uuid
import time
import threading
import json
import logging
import re
from urllib.parse import urlparse, unquote
from functools import lru_cache
from datetime import datetime, timedelta
import hashlib

# ---------------- LOGGING ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
Compress(app)  # Enable gzip compression

# ---------------- CACHED INDEX.HTML ----------------
_cached_index = None
_index_mtime = None

def get_cached_index():
    """Cache index.html in memory for performance"""
    global _cached_index, _index_mtime
    try:
        current_mtime = os.path.getmtime("index.html")
        if _cached_index is None or _index_mtime != current_mtime:
            with open("index.html", "r", encoding="utf-8") as f:
                _cached_index = f.read()
            _index_mtime = current_mtime
        return _cached_index
    except Exception as e:
        logger.error(f"Error reading index.html: {e}")
        return None

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
    res.headers['X-XSS-Protection'] = '1; mode=block'
    res.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return res

# ---------------- TRACKING DATA STORE ----------------
TRACKING_FILE = "tracking_data.json"
_tracking_cache = None
_tracking_mtime = None

def load_tracking_data():
    """Load tracking data from JSON file"""
    global _tracking_cache, _tracking_mtime
    try:
        current_mtime = os.path.getmtime(TRACKING_FILE) if os.path.exists(TRACKING_FILE) else None
        if _tracking_mtime != current_mtime:
            if os.path.exists(TRACKING_FILE):
                with open(TRACKING_FILE, "r", encoding="utf-8") as f:
                    _tracking_cache = json.load(f)
            else:
                _tracking_cache = {"events": [], "downloads": 0, "page_views": {}}
            _tracking_mtime = current_mtime
        return _tracking_cache
    except Exception as e:
        logger.error(f"Error loading tracking data: {e}")
        return {"events": [], "downloads": 0, "page_views": {}}

def save_tracking_data(data):
    """Save tracking data to JSON file"""
    global _tracking_cache, _tracking_mtime
    try:
        with open(TRACKING_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        _tracking_cache = data
        _tracking_mtime = os.path.getmtime(TRACKING_FILE)
    except Exception as e:
        logger.error(f"Error saving tracking data: {e}")

def get_device_type(user_agent):
    """Detect device type from user agent"""
    ua = user_agent.lower()
    if any(x in ua for x in ['mobile', 'android', 'iphone', 'ipad']):
        return 'mobile'
    return 'desktop'

# ---------------- SEO DATA - MANUAL OVERRIDES FOR TOP PAGES ----------------
SEO_PAGES = {
    "": {
        "title": "Download Instagram Reels Without Watermark (Free) | ReelSnag",
        "description": "Download Instagram reels without watermark in HD quality. Free, fast and secure Instagram reel downloader. Paste link and download instantly with ReelSnag.",
        "heading": "Download Instagram Reels",
        "subtitle": "Paste your reel link and download instantly",
        "content": "ReelSnag is a free Instagram reel downloader that allows users to download reels without watermark in HD quality. Works instantly on all devices."
    },
    "download-instagram-reels": {
        "title": "Download Instagram Reels Free HD | ReelSnag",
        "description": "Download Instagram reels free in HD with no watermark using ReelSnag. Fast, secure, and works on all devices.",
        "heading": "Download Instagram Reels",
        "subtitle": "Free HD reel downloader online",
        "content": "Download Instagram reels in HD quality without any watermark. Our free tool works instantly on mobile and desktop."
    },
    "reels-downloader": {
        "title": "Best Reels Downloader Online | ReelSnag",
        "description": "Best reels downloader to save Instagram videos instantly without watermark. Free HD downloads.",
        "heading": "Reels Downloader",
        "subtitle": "Fast and free, no watermark",
        "content": "The best reels downloader tool for Instagram. Download unlimited reels in HD quality for free."
    },
    "instagram-reel-downloader": {
        "title": "Instagram Reel Downloader Without Watermark HD | ReelSnag",
        "description": "Download Instagram reels without watermark in HD quality using ReelSnag. Free and instant.",
        "heading": "Instagram Reel Downloader",
        "subtitle": "Download reels without watermark in HD",
        "content": "Professional Instagram reel downloader with no watermark. Get HD quality downloads instantly."
    },
    "hd-reels-downloader": {
        "title": "HD Reels Downloader - Download Instagram in High Quality | ReelSnag",
        "description": "Download Instagram reels in HD quality with our HD reels downloader. Full resolution, no compression.",
        "heading": "HD Reels Downloader",
        "subtitle": "Download in full HD quality",
        "content": "Download Instagram reels in the highest quality available. Our HD downloader preserves original resolution."
    },
    "no-watermark-reels": {
        "title": "Download Reels Without Watermark | ReelSnag",
        "description": "Download Instagram reels without watermark. Clean, professional downloads with zero branding.",
        "heading": "No Watermark Reels",
        "subtitle": "Clean downloads, zero branding",
        "content": "Get clean reel downloads without any watermark or branding. Perfect for content creators."
    },
    "free-reels-downloader": {
        "title": "Free Reels Downloader - Unlimited Downloads | ReelSnag",
        "description": "Free reels downloader with unlimited downloads. No subscription, no limits, no signup required.",
        "heading": "Free Reels Downloader",
        "subtitle": "Unlimited, no subscription",
        "content": "Download unlimited Instagram reels for free. No subscription, no hidden costs, completely free forever."
    },
    "reels-downloader-android": {
        "title": "Reels Downloader for Android | ReelSnag",
        "description": "Download reels on Android devices. Works with Chrome, Firefox, and all Android browsers.",
        "heading": "Reels Downloader for Android",
        "subtitle": "Works on all Android devices",
        "content": "Best reels downloader for Android phones and tablets. Works seamlessly in any Android browser."
    },
    "reels-downloader-iphone": {
        "title": "Reels Downloader for iPhone | ReelSnag",
        "description": "Download reels on iPhone and iPad. Works with Safari and iOS browsers without apps.",
        "heading": "Reels Downloader for iPhone",
        "subtitle": "Works on iOS without apps",
        "content": "Download Instagram reels on iPhone and iPad. No app required, works directly in Safari."
    },
    "download-instagram-reels-india": {
        "title": "Download Instagram Reels India | ReelSnag",
        "description": "Fast Instagram reel downloads for India users. Optimized for Jio and Airtel networks.",
        "heading": "Download Instagram Reels India",
        "subtitle": "Fast for Jio & Airtel users",
        "content": "Lightning-fast reel downloads for Indian users. Optimized for Jio, Airtel, and Vi networks."
    },
    "4k-reels": {
        "title": "4K Reels Downloader - Ultra HD Instagram Downloads | ReelSnag",
        "description": "Download Instagram reels in 4K ultra HD quality. Highest resolution reel downloader available.",
        "heading": "4K Reels Downloader",
        "subtitle": "Ultra HD quality downloads",
        "content": "Download Instagram reels in stunning 4K resolution. Get the highest quality downloads possible."
    },
    "fast-reels": {
        "title": "Fast Reels Downloader - Instant Downloads | ReelSnag",
        "description": "Fastest Instagram reel downloader. Instant processing and quick downloads in seconds.",
        "heading": "Fast Reels Downloader",
        "subtitle": "Lightning-fast downloads",
        "content": "The fastest reel downloader available. Process and download reels in seconds, not minutes."
    },
    "instant-reels": {
        "title": "Instant Reels - Download Instagram Reels Instantly | ReelSnag",
        "description": "Instant Instagram reel downloads with zero waiting. Process and download in one click.",
        "heading": "Instant Reels Downloader",
        "subtitle": "Zero waiting, instant download",
        "content": "Get instant reel downloads with our one-click downloader. No waiting, no delays."
    },
    "reels-downloader-pc": {
        "title": "Reels Downloader for PC - Windows & Mac | ReelSnag",
        "description": "Download Instagram reels on Windows PC and Mac. Works in any desktop browser.",
        "heading": "Reels Downloader for PC",
        "subtitle": "Windows and Mac compatible",
        "content": "Download Instagram reels on your PC or Mac. Works in Chrome, Firefox, Safari, and Edge."
    },
    "reels-downloader-jio": {
        "title": "Jio Reels Downloader - Fast Downloads in India | ReelSnag",
        "description": "Fast Instagram reel downloads on Jio network. Optimized for Indian users.",
        "heading": "Jio Reels Downloader",
        "subtitle": "Optimized for Jio network",
        "content": "Lightning-fast reel downloads on Jio 4G and 5G networks. Made for Indian users."
    },
    "reels-downloader-airtel": {
        "title": "Airtel Reels Downloader - Fast Downloads | ReelSnag",
        "description": "Fast Instagram reel downloads on Airtel network. High-speed downloads for India.",
        "heading": "Airtel Reels Downloader",
        "subtitle": "Optimized for Airtel network",
        "content": "High-speed reel downloads on Airtel 4G and 5G. Perfect for Indian users."
    }
}

# ---------------- KEYWORD DETECTION FOR DYNAMIC SEO ----------------
SEO_KEYWORDS = {
    'quality': ['hd', '4k', 'ultra', 'high-quality', 'full-hd', '1080p', '720p'],
    'no_watermark': ['no-watermark', 'without-watermark', 'clean', 'no-branding'],
    'pricing': ['free', 'unlimited', 'no-subscription'],
    'speed': ['fast', 'instant', 'quick', 'speed', 'lightning', 'rapid'],
    'geo_india': ['india', 'indian', 'jio', 'airtel', 'vi', 'mumbai', 'delhi'],
    'device_android': ['android', 'samsung', 'pixel', 'oneplus', 'xiaomi'],
    'device_ios': ['iphone', 'ipad', 'ios', 'apple'],
    'device_pc': ['pc', 'windows', 'mac', 'desktop', 'laptop'],
    'platform_instagram': ['instagram', 'insta', 'ig', 'reels', 'reel']
}

def detect_intent_keywords(slug):
    """Detect intent keywords from slug to generate appropriate SEO content"""
    slug_lower = slug.lower().replace('_', '-')
    intents = {
        'quality': False,
        'no_watermark': False,
        'pricing': False,
        'speed': False,
        'geo_india': False,
        'device_android': False,
        'device_ios': False,
        'device_pc': False
    }

    for intent, keywords in SEO_KEYWORDS.items():
        for keyword in keywords:
            if keyword in slug_lower:
                intents[intent] = True
                break

    return intents

def slug_to_title(slug):
    """Convert slug to readable title"""
    return slug.replace('-', ' ').replace('_', ' ').title()

def generate_dynamic_seo(slug):
    """Generate SEO content dynamically for any slug"""
    intents = detect_intent_keywords(slug)
    title_base = slug_to_title(slug)

    # Build title based on intents
    title_parts = [title_base]
    if intents['quality']:
        title_parts.append("HD Quality")
    if intents['no_watermark']:
        title_parts.append("Without Watermark")
    if intents['pricing'] == 'free':
        title_parts.append("Free")
    if intents['speed']:
        title_parts.append("Fast")
    if intents['geo_india']:
        title_parts.append("India")

    title = " | ".join(title_parts) + " | ReelSnag"

    # Build description
    desc_parts = []
    if intents['quality']:
        desc_parts.append("Download Instagram reels in HD quality")
    elif intents['no_watermark']:
        desc_parts.append("Download reels without watermark")
    else:
        desc_parts.append("Download Instagram reels")

    if intents['geo_india']:
        desc_parts.append("optimized for India users")
    if intents['device_android']:
        desc_parts.append("works on Android devices")
    elif intents['device_ios']:
        desc_parts.append("works on iPhone and iPad")
    elif intents['device_pc']:
        desc_parts.append("works on PC and Mac")
    if intents['speed']:
        desc_parts.append("fast and instant downloads")

    description = ". ".join(desc_parts) + ". Free tool by ReelSnag."

    # Build heading
    heading = title_base

    # Build subtitle
    subtitle_parts = []
    if intents['pricing']:
        subtitle_parts.append("Free")
    if intents['speed']:
        subtitle_parts.append("Fast")
    if intents['quality']:
        subtitle_parts.append("HD Quality")
    if intents['no_watermark']:
        subtitle_parts.append("No Watermark")
    subtitle = ", ".join(subtitle_parts) if subtitle_parts else "Download reels instantly"

    # Build content paragraph
    content = f"Download {title_base.lower()} with ReelSnag. "
    if intents['quality']:
        content += "Get high-quality HD downloads with original resolution. "
    if intents['no_watermark']:
        content += "Clean downloads without any watermark or branding. "
    if intents['speed']:
        content += "Lightning-fast processing and instant downloads. "
    if intents['geo_india']:
        content += "Optimized for fast downloads in India on Jio and Airtel networks. "
    content += "Free, no signup required."

    return {
        "title": title.strip(),
        "description": description.strip(),
        "heading": heading,
        "subtitle": subtitle,
        "content": content.strip()
    }

def get_seo_for_slug(slug):
    """Get SEO data - manual override first, then dynamic generation"""
    if slug in SEO_PAGES:
        return SEO_PAGES[slug]
    return generate_dynamic_seo(slug)

# ---------------- GENERATE ALL SEO SLUGS (200-500) ----------------
def generate_all_seo_slugs():
    """Generate 200-500 SEO slugs programmatically"""
    base_slugs = list(SEO_PAGES.keys())

    # Quality variations
    quality_terms = ['hd', '4k', 'full-hd', '1080p', '720p', 'ultra-hd', 'high-quality']
    # Speed variations
    speed_terms = ['fast', 'instant', 'quick', 'rapid', 'lightning']
    # Device variations
    device_terms = ['android', 'iphone', 'ipad', 'pc', 'windows', 'mac', 'desktop', 'mobile']
    # Geo variations
    geo_terms = ['india', 'usa', 'uk', 'canada', 'australia', 'pakistan', 'bangladesh']
    # Network variations
    network_terms = ['jio', 'airtel', 'vi', 'verizon', 'att', 'tmobile']
    # Feature variations
    feature_terms = ['no-watermark', 'without-watermark', 'free', 'unlimited', 'online']

    generated = set(base_slugs)

    # Generate combinations
    for quality in quality_terms:
        generated.add(f"{quality}-reels")
        generated.add(f"{quality}-reels-downloader")

    for speed in speed_terms:
        generated.add(f"{speed}-reels")
        generated.add(f"{speed}-reels-downloader")

    for device in device_terms:
        generated.add(f"reels-downloader-{device}")
        generated.add(f"download-reels-{device}")

    for geo in geo_terms:
        generated.add(f"reels-downloader-{geo}")
        generated.add(f"download-reels-{geo}")

    for network in network_terms:
        generated.add(f"reels-downloader-{network}")

    for feature in feature_terms:
        generated.add(f"{feature}-reels")
        generated.add(f"{feature}-reels-downloader")

    # Combined variations
    for quality in quality_terms[:3]:
        for device in device_terms[:3]:
            generated.add(f"{quality}-reels-{device}")

    for speed in speed_terms[:2]:
        for geo in geo_terms[:2]:
            generated.add(f"{speed}-reels-{geo}")

    return sorted(list(generated))

ALL_SEO_SLUGS = generate_all_seo_slugs()

       # Inject SEO data for frontend (SAFE - no duplication)
@lru_cache(maxsize=100)
def inject_seo_cached(html, slug):
    try:
        seo = get_seo_for_slug(slug)
        canonical = "https://reelsnag.site/" if slug == "" else f"https://reelsnag.site/{slug}"

        # 🔥 YOUR FIX GOES HERE (INSIDE TRY)
        script = f'<script>window.SERVER_SEO={json.dumps(seo)}</script>'

        if "window.SERVER_SEO" not in html and "</head>" in html:
            html = html.replace("</head>", script + "\n</head>")

        # other SEO replacements...
        try:
            html = re.sub(r"<title>.*?</title>", f"<title>{seo['title']}</title>", html, count=1)
        except:
            pass

        try:
            html = re.sub(r'<link rel="canonical".*?>', f'<link rel="canonical" href="{canonical}" />', html, count=1)
        except:
            pass

        return html

    except Exception as e:
        logger.error(f"SEO injection error: {e}")
        return html
# ---------------- ROUTES ----------------

@app.route('/')
def home():
    html = get_cached_index()
    if html is None:
        return "Error loading page", 500
    return inject_seo_cached(html, "")

@app.route('/<slug>')
def seo_page(slug):
    try:
        html = get_cached_index()
        if html is None:
            return "Error loading page", 500
        return make_response(inject_seo_cached(html, slug))
    except Exception as e:
        logger.error(f"SEO page error: {e}")
        return "Error", 500

@app.route('/sitemap.xml')
def sitemap():
    """Generate dynamic sitemap with all SEO pages"""
    now = datetime.now().strftime("%Y-%m-%d")

    urls = []
    for slug in ALL_SEO_SLUGS:
        loc = f"https://reelsnag.site/{slug}" if slug else "https://reelsnag.site/"
        urls.append(f'  <url>\n    <loc>{loc}</loc>\n    <lastmod>{now}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>')

    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap_xml += '\n'.join(urls)
    sitemap_xml += '\n</urlset>'

    return Response(sitemap_xml, mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    """Robots.txt for SEO"""
    content = """User-agent: *
Allow: /
Sitemap: https://reelsnag.site/sitemap.xml
"""
    return Response(content, mimetype='text/plain')

@app.route('/privacy-policy')
def privacy():
    return """
    <h1>Privacy Policy</h1>
    <p>ReelSnag does not store personal data. We may collect anonymous usage data to improve the service.</p>
    <p>We use cookies and analytics tools to understand user behavior.</p>
    <p>By using this website, you agree to this policy.</p>
    """

@app.route('/terms')
def terms():
    return """
    <h1>Terms & Conditions</h1>
    <p>This tool is provided for personal use only.</p>
    <p>Users are responsible for ensuring they have rights to download content.</p>
    <p>ReelSnag is not responsible for misuse of this tool.</p>
    """

@app.route('/about')
def about():
    return """
    <h1>About ReelSnag</h1>
    <p>ReelSnag is a free tool to download Instagram reels without watermark in HD quality.</p>
    <p>It is fast, secure, and works on all devices.</p>
    """

@app.route('/contact')
def contact():
    return """
    <h1>Contact</h1>
    <p>For inquiries, contact: reelsnag.site@email.com</p>
    """

# ---------------- TRACK ENDPOINT (ENHANCED) ----------------
@app.route('/track', methods=['POST'])
def track():
    try:
        data = request.get_json(force=True, silent=True) or {}

        user_agent = request.headers.get('User-Agent', 'unknown')
        referrer = request.headers.get('Referer', 'direct')
        device_type = get_device_type(user_agent)

        track_data = {
            'event': data.get('event', 'pageview'),
            'page': data.get('page', request.path),
            'slug': data.get('page', request.path).lstrip('/'),
            'timestamp': datetime.now().isoformat(),
            'user_agent': user_agent,
            'device_type': device_type,
            'referrer': referrer,
            'ip': request.remote_addr,
            'success': data.get('success', True),
            'extra': data.get('extra', {})
        }

        tracking = load_tracking_data()

        if not isinstance(tracking.get('page_views'), dict):
            tracking['page_views'] = {}

        if not isinstance(tracking.get('events'), list):
            tracking['events'] = []

        if not isinstance(tracking.get('downloads'), int):
            tracking['downloads'] = 0

        tracking['events'].append(track_data)

        if track_data['event'] == 'pageview':
            page = track_data['page']
            if page not in tracking['page_views']:
                tracking['page_views'][page] = 0
            tracking['page_views'][page] += 1

        if track_data['event'] == 'download_success':
            tracking['downloads'] += 1

        save_tracking_data(tracking)

        return jsonify({"ok": True})

    except Exception as e:
        logger.error(f"Track error: {e}")
        return jsonify({"ok": True})
# ---------------- STATS ENDPOINT ----------------
@app.route('/stats')
def stats():
    """Return analytics data"""
    tracking = load_tracking_data()

    # Calculate top pages
    page_views = tracking.get('page_views', {})
    top_pages = sorted(page_views.items(), key=lambda x: x[1], reverse=True)[:10]

    # Recent activity (last 50 events)
    recent = tracking.get('events', [])[-50:]

    # Device breakdown
    device_counts = {'mobile': 0, 'desktop': 0}
    for event in tracking.get('events', [])[-1000:]:
        dt = event.get('device_type', 'desktop')
        device_counts[dt] = device_counts.get(dt, 0) + 1

    stats_data = {
        'total_downloads': tracking.get('downloads', 0),
        'total_page_views': sum(page_views.values()),
        'unique_pages': len(page_views),
        'top_pages': [{'page': p, 'views': v} for p, v in top_pages],
        'recent_activity': recent,
        'device_breakdown': device_counts,
        'total_events': len(tracking.get('events', []))
    }

    return jsonify(stats_data)

# ---------------- DOWNLOAD ---------------
       @app.route('/download', methods=['POST'])
def download():
    ip = request.remote_addr or "unknown"

    if not check_rate_limit(ip):
        return jsonify({"error": "Too many requests. Please wait."}), 429

    try:
        data = request.get_json(silent=True) or {}
        url = data.get("url", "").strip()

        if not url or "instagram.com" not in url:
            return jsonify({"error": "Invalid Instagram URL"}), 400

        tmp_dir = "/tmp/reelsnag" if os.name != 'nt' else os.path.join(os.environ.get('TEMP', '.'), 'reelsnag')
        os.makedirs(tmp_dir, exist_ok=True)

        file_id = str(uuid.uuid4())
        path = os.path.join(tmp_dir, file_id)

        ydl_opts = {
            'outtmpl': path + '.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'format': 'best[ext=mp4]/best',
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        return send_file(
            file_path,
            as_attachment=True,
            download_name="reelsnag_download.mp4",
            mimetype="video/mp4"
        )

    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({"error": "Download failed"}), 500
# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, threaded=True)
