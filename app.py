from flask import Flask, request, jsonify, send_file, Response, make_response
import yt_dlp
import os
import uuid
import time
import threading
import json
import logging
import re
from urllib.parse import urlparse
from functools import lru_cache
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# In-memory rate limiting storage
rate_limit_store = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 10  # max downloads per window per IP

# Cleanup old rate limit entries periodically
def cleanup_rate_limits():
    now = datetime.now()
    to_delete = [ip for ip, data in rate_limit_store.items()
                 if data['window_start'] + timedelta(seconds=RATE_LIMIT_WINDOW * 2) < now]
    for ip in to_delete:
        del rate_limit_store[ip]

# Start cleanup thread
def rate_limit_cleanup_thread():
    while True:
        time.sleep(300)  # Clean every 5 minutes
        cleanup_rate_limits()

threading.Thread(target=rate_limit_cleanup_thread, daemon=True).start()


def check_rate_limit(ip):
    """Check if IP has exceeded rate limit. Returns True if allowed."""
    now = datetime.now()

    if ip not in rate_limit_store:
        rate_limit_store[ip] = {'count': 1, 'window_start': now}
        return True

    data = rate_limit_store[ip]

    # Reset window if expired
    if data['window_start'] + timedelta(seconds=RATE_LIMIT_WINDOW) < now:
        rate_limit_store[ip] = {'count': 1, 'window_start': now}
        return True

    # Check limit
    if data['count'] >= RATE_LIMIT_MAX:
        return False

    # Increment count
    data['count'] += 1
    return True


@app.after_request
def add_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

    # Add cache control for SEO pages
    if request.path != '/download' and request.path != '/track':
        response.headers['Cache-Control'] = 'public, max-age=3600, stale-while-revalidate=86400'

    return response


# =============================================================================
# SEO PAGES CONFIGURATION - Programmatic SEO at Scale
# =============================================================================
SEO_PAGES = {
    # Core keyword pages
    "download-instagram-reels": {
        "title": "Download Instagram Reels Free HD | ReelSnag",
        "description": "Download Instagram reels free in HD with no watermark using ReelSnag. Fast, secure, and unlimited downloads. Works on all devices.",
        "heading": "Download Instagram Reels",
        "subtitle": "Free HD reel downloader online",
        "content": "Download Instagram reels free in HD with no watermark using ReelSnag. Our tool works instantly on all devices - no login required.",
        "keywords": "download instagram reels, instagram reels download, free reel downloader",
        "h1_extra": "Without Watermark in HD",
    },
    "reels-downloader": {
        "title": "Best Reels Downloader Online | ReelSnag",
        "description": "Best reels downloader to save Instagram videos instantly without watermark. Fast, free, and works on mobile and desktop.",
        "heading": "Reels Downloader",
        "subtitle": "Fast and free reel downloader",
        "content": "Best reels downloader to save Instagram videos instantly without watermark. Works on Android, iPhone, Windows, and Mac.",
        "keywords": "reels downloader, instagram reels downloader, best reel downloader",
        "h1_extra": "For All Devices",
    },
    "instagram-reel-downloader": {
        "title": "Instagram Reel Downloader Without Watermark HD | ReelSnag",
        "description": "Download Instagram reels without watermark in HD quality using ReelSnag. Free, fast, and secure reel saver.",
        "heading": "Instagram Reel Downloader",
        "subtitle": "Download reels without watermark in HD",
        "content": "Download Instagram reels without watermark in HD quality using ReelSnag. Fast and free tool that works instantly.",
        "keywords": "instagram reel downloader, reel downloader, instagram video downloader",
        "h1_extra": "Fast & Free",
    },
    "save-instagram-reels": {
        "title": "Save Instagram Reels - Download & Keep Forever | ReelSnag",
        "description": "Save Instagram reels permanently. Download and keep your favorite reels offline with ReelSnag. Free and unlimited.",
        "heading": "Save Instagram Reels",
        "subtitle": "Download and keep reels forever",
        "content": "Save Instagram reels permanently to your device. Download and keep your favorite reels offline with ReelSnag - free and unlimited.",
        "keywords": "save instagram reels, keep reels, download reels permanently",
        "h1_extra": "Offline Forever",
    },
    "instagram-video-saver": {
        "title": "Instagram Video Saver - Download Reels & Videos | ReelSnag",
        "description": "Instagram video saver to download reels, stories, and videos. Free tool with no limits. HD quality guaranteed.",
        "heading": "Instagram Video Saver",
        "subtitle": "Save any Instagram video instantly",
        "content": "Instagram video saver to download reels, stories, and videos. Free tool with no limits. HD quality guaranteed.",
        "keywords": "instagram video saver, save instagram video, instagram downloader",
        "h1_extra": "No Limits",
    },
    # Quality-focused pages
    "hd-reels-downloader": {
        "title": "HD Reels Downloader - Download Instagram in High Quality | ReelSnag",
        "description": "Download Instagram reels in HD quality. High definition reel downloader with no compression. Free and fast.",
        "heading": "HD Reels Downloader",
        "subtitle": "Download in full HD quality",
        "content": "Download Instagram reels in HD quality. Our high definition reel downloader preserves original quality with no compression.",
        "keywords": "hd reels downloader, high quality reels, 1080p reels download",
        "h1_extra": "1080p Quality",
    },
    "no-watermark-reels": {
        "title": "Download Reels Without Watermark | ReelSnag",
        "description": "Download Instagram reels without watermark. Clean videos with no logo or branding. 100% free.",
        "heading": "No Watermark Reels",
        "subtitle": "Clean downloads, zero branding",
        "content": "Download Instagram reels without watermark. Get clean videos with no logo or branding. 100% free and unlimited.",
        "keywords": "no watermark reels, clean reels download, watermark free reels",
        "h1_extra": "Clean Videos",
    },
    "4k-reels-download": {
        "title": "4K Reels Download - Ultra HD Instagram Videos | ReelSnag",
        "description": "Download Instagram reels in 4K ultra HD quality. Best quality reel downloader available. Free and fast.",
        "heading": "4K Reels Download",
        "subtitle": "Ultra HD quality when available",
        "content": "Download Instagram reels in 4K ultra HD quality when available. Best quality reel downloader with original resolution preserved.",
        "keywords": "4k reels download, ultra hd reels, highest quality reels",
        "h1_extra": "Maximum Quality",
    },
    # Platform-specific pages
    "reels-downloader-android": {
        "title": "Reels Downloader for Android - Download Instagram Reels | ReelSnag",
        "description": "Reels downloader for Android phones and tablets. Download Instagram reels on any Android device. Free app alternative.",
        "heading": "Reels Downloader for Android",
        "subtitle": "Works on all Android devices",
        "content": "Reels downloader for Android phones and tablets. Download Instagram reels on any Android device without installing an app.",
        "keywords": "reels downloader android, android reel download, instagram android",
        "h1_extra": "No App Needed",
    },
    "reels-downloader-iphone": {
        "title": "Reels Downloader for iPhone - Download Instagram Reels iOS | ReelSnag",
        "description": "Reels downloader for iPhone and iPad. Download Instagram reels on iOS without apps. Free and easy.",
        "heading": "Reels Downloader for iPhone",
        "subtitle": "Works on iOS without apps",
        "content": "Reels downloader for iPhone and iPad. Download Instagram reels on iOS without installing any apps. Free and easy to use.",
        "keywords": "reels downloader iphone, ios reel download, iphone instagram reels",
        "h1_extra": "iOS Compatible",
    },
    "reels-downloader-pc": {
        "title": "Reels Downloader for PC - Download Instagram on Windows/Mac | ReelSnag",
        "description": "Reels downloader for PC, Windows, and Mac. Download Instagram reels on desktop. No software needed.",
        "heading": "Reels Downloader for PC",
        "subtitle": "Desktop download made easy",
        "content": "Reels downloader for PC, Windows, and Mac. Download Instagram reels on desktop without any software installation.",
        "keywords": "reels downloader pc, windows reel download, mac instagram reels",
        "h1_extra": "Desktop Ready",
    },
    "mobile-reels-downloader": {
        "title": "Mobile Reels Downloader - Download on Phone | ReelSnag",
        "description": "Mobile reels downloader optimized for phones. Download Instagram reels on any mobile browser. Fast and free.",
        "heading": "Mobile Reels Downloader",
        "subtitle": "Optimized for mobile browsers",
        "content": "Mobile reels downloader optimized for phones. Download Instagram reels on any mobile browser. Fast, free, and data-friendly.",
        "keywords": "mobile reels downloader, phone reel download, mobile instagram",
        "h1_extra": "Mobile First",
    },
    # Location-specific pages
    "download-instagram-reels-india": {
        "title": "Download Instagram Reels India | ReelSnag",
        "description": "Download Instagram reels in India without watermark. Fast for Jio and Airtel users. Free reel downloader.",
        "heading": "Download Instagram Reels India",
        "subtitle": "Fast for Jio & Airtel users",
        "content": "Download Instagram reels in India without watermark. Optimized for Indian users with fast speeds on Jio and Airtel networks.",
        "keywords": "instagram reels india, download reels india, indian reel downloader",
        "h1_extra": "Made for India",
    },
    "hindi-reels-downloader": {
        "title": "Hindi Reels Downloader - Download Indian Reels | ReelSnag",
        "description": "Hindi reels downloader for Bollywood and Indian content. Download Hindi Instagram reels in HD. Free tool.",
        "heading": "Hindi Reels Downloader",
        "subtitle": "Bollywood and Indian content",
        "content": "Hindi reels downloader for Bollywood and Indian content. Download Hindi Instagram reels in HD quality. Free and unlimited.",
        "keywords": "hindi reels downloader, bollywood reels, indian instagram reels",
        "h1_extra": "Desi Content",
    },
    "usa-reels-downloader": {
        "title": "USA Reels Downloader - Download Instagram Reels US | ReelSnag",
        "description": "USA reels downloader for American users. Download Instagram reels in the US. Fast and reliable.",
        "heading": "USA Reels Downloader",
        "subtitle": "Optimized for US users",
        "content": "USA reels downloader for American users. Download Instagram reels in the US with fast speeds and reliable service.",
        "keywords": "usa reels downloader, american reels, us instagram download",
        "h1_extra": "US Optimized",
    },
    # Intent-based pages
    "free-reels-downloader": {
        "title": "Free Reels Downloader - Unlimited Downloads | ReelSnag",
        "description": "Free reels downloader with unlimited downloads. No subscription, no limits. Download as many reels as you want.",
        "heading": "Free Reels Downloader",
        "subtitle": "Unlimited, no subscription",
        "content": "Free reels downloader with unlimited downloads. No subscription, no hidden fees. Download as many reels as you want, completely free.",
        "keywords": "free reels downloader, unlimited reels, no subscription downloader",
        "h1_extra": "100% Free Forever",
    },
    "fast-reels-downloader": {
        "title": "Fast Reels Downloader - Instant Downloads | ReelSnag",
        "description": "Fast reels downloader with instant processing. Download Instagram reels in seconds. Quick and efficient.",
        "heading": "Fast Reels Downloader",
        "subtitle": "Lightning-fast processing",
        "content": "Fast reels downloader with instant processing. Download Instagram reels in seconds. Quick, efficient, and reliable.",
        "keywords": "fast reels downloader, instant reel download, quick downloader",
        "h1_extra": "Seconds, Not Minutes",
    },
    "online-reels-downloader": {
        "title": "Online Reels Downloader - No Installation Required | ReelSnag",
        "description": "Online reels downloader that works in any browser. No installation or app required. Download reels directly from web.",
        "heading": "Online Reels Downloader",
        "subtitle": "No installation required",
        "content": "Online reels downloader that works in any browser. No installation or app required. Download reels directly from the web.",
        "keywords": "online reels downloader, web reel download, browser downloader",
        "h1_extra": "Browser-Based",
    },
    "reels-downloader-2026": {
        "title": "Reels Downloader 2026 - Latest Version | ReelSnag",
        "description": "Reels downloader 2026 version. Latest features and improvements. Download Instagram reels with the newest technology.",
        "heading": "Reels Downloader 2026",
        "subtitle": "Latest version, newest features",
        "content": "Reels downloader 2026 version with latest features and improvements. Download Instagram reels using the newest technology and fastest speeds.",
        "keywords": "reels downloader 2026, latest reel downloader, new instagram downloader",
        "h1_extra": "Current Year",
    },
    "reels-without-login": {
        "title": "Download Reels Without Login - No Sign Up | ReelSnag",
        "description": "Download reels without login or sign up. No account needed. Private and anonymous reel downloads.",
        "heading": "Reels Without Login",
        "subtitle": "No account, no signup",
        "content": "Download reels without login or sign up. No account needed. Private and anonymous reel downloads with no registration required.",
        "keywords": "reels without login, no signup reels, anonymous reel download",
        "h1_extra": "No Account Needed",
    },
}


# =============================================================================
# SEO CONTENT TEMPLATES - Deep, Useful Content Per Page
# =============================================================================
def get_seo_content(slug):
    """Generate detailed SEO content for each page."""

    base_content = {
        "how_it_works": """
            <h3>How to Download Instagram Reels</h3>
            <ol>
                <li>Copy the Instagram reel link you want to download</li>
                <li>Paste it into the input box above</li>
                <li>Click the Download button</li>
                <li>Your reel will be processed and downloaded in HD quality</li>
            </ol>
        """,
        "supported_devices": """
            <h3>Supported Devices</h3>
            <p>ReelSnag works on all devices:</p>
            <ul>
                <li><strong>Android:</strong> All versions, Chrome/Firefox/Samsung browser</li>
                <li><strong>iPhone/iPad:</strong> iOS 12+, Safari/Chrome</li>
                <li><strong>Windows PC:</strong> Windows 10/11, any browser</li>
                <li><strong>Mac:</strong> macOS 10.14+, Safari/Chrome/Firefox</li>
                <li><strong>Linux:</strong> All distributions with modern browsers</li>
            </ul>
        """,
        "supported_formats": """
            <h3>Supported Formats</h3>
            <p>We download reels in the best available quality:</p>
            <ul>
                <li><strong>Video:</strong> MP4 (H.264 codec)</li>
                <li><strong>Quality:</strong> Up to 1080p HD (4K when available)</li>
                <li><strong>Audio:</strong> AAC stereo, original quality</li>
                <li><strong>No watermark:</strong> Clean video without branding</li>
            </ul>
        """,
        "safety": """
            <h3>Safe & Private</h3>
            <p>Your privacy matters:</p>
            <ul>
                <li>No login or signup required</li>
                <li>No personal data collected</li>
                <li>Downloads are processed securely</li>
                <li>No tracking of your download history</li>
                <li>We don't store your downloaded videos</li>
            </ul>
        """,
        "troubleshooting": """
            <h3>Troubleshooting</h3>
            <p>If download fails:</p>
            <ul>
                <li>Check that the Instagram link is correct and complete</li>
                <li>Ensure the reel is public (not from a private account)</li>
                <li>Try refreshing the page and pasting again</li>
                <li>Clear your browser cache if issues persist</li>
                <li>Check your internet connection</li>
            </ul>
        """,
    }

    # Page-specific FAQs
    faqs = {
        "download-instagram-reels": [
            {"q": "Is it free to download Instagram reels?", "a": "Yes, ReelSnag is 100% free with unlimited downloads."},
            {"q": "Do I need to install anything?", "a": "No, our tool works entirely in your browser."},
            {"q": "Can I download private reels?", "a": "No, only public reels can be downloaded."},
            {"q": "What quality are the downloads?", "a": "Reels are downloaded in the highest available quality, up to 1080p HD."},
        ],
        "reels-downloader": [
            {"q": "What is the best reels downloader?", "a": "ReelSnag is fast, free, and works without watermarks."},
            {"q": "Does it work on mobile?", "a": "Yes, works perfectly on Android and iPhone."},
            {"q": "Is there a download limit?", "a": "No limit - download as many reels as you want."},
        ],
        "instagram-reel-downloader": [
            {"q": "How do I download reels from Instagram?", "a": "Copy the reel link, paste it here, and click download."},
            {"q": "Are reels downloaded without watermark?", "a": "Yes, all downloads are without any watermark."},
            {"q": "Can I download on iPhone?", "a": "Yes, works on all iPhones and iPads."},
        ],
        "hd-reels-downloader": [
            {"q": "What is HD quality for reels?", "a": "HD means 720p or 1080p resolution, the highest Instagram offers."},
            {"q": "Do all reels download in HD?", "a": "We download in the highest quality available for that reel."},
            {"q": "Is HD download free?", "a": "Yes, HD downloads are completely free."},
        ],
        "no-watermark-reels": [
            {"q": "Are all downloads without watermark?", "a": "Yes, 100% watermark-free guaranteed."},
            {"q": "Why remove watermark?", "a": "Clean videos are better for personal use and editing."},
        ],
        "reels-downloader-android": [
            {"q": "Do I need an Android app?", "a": "No app needed - works directly in your mobile browser."},
            {"q": "Which Android browsers work?", "a": "Chrome, Firefox, Samsung Internet, and all major browsers."},
        ],
        "reels-downloader-iphone": [
            {"q": "Do I need an iOS app?", "a": "No, works in Safari without any app installation."},
            {"q": "Where are downloads saved on iPhone?", "a": "In the Files app under Downloads."},
        ],
        "download-instagram-reels-india": [
            {"q": "Is this optimized for India?", "a": "Yes, fast speeds on Jio, Airtel, and Vi networks."},
            {"q": "Can I download Bollywood reels?", "a": "Yes, any public Instagram reel can be downloaded."},
        ],
        "free-reels-downloader": [
            {"q": "Is this really free?", "a": "100% free, no hidden charges or subscriptions."},
            {"q": "How many reels can I download?", "a": "Unlimited downloads, no daily limits."},
        ],
        "fast-reels-downloader": [
            {"q": "How fast is the download?", "a": "Processing takes 2-5 seconds, then instant download."},
            {"q": "What affects download speed?", "a": "Your internet connection and reel length."},
        ],
    }

    # Default FAQs for pages without specific ones
    default_faqs = [
        {"q": "Is ReelSnag free to use?", "a": "Yes, completely free with no limits."},
        {"q": "Do I need to create an account?", "a": "No account or login required."},
        {"q": "Are downloads watermark-free?", "a": "Yes, all downloads are without watermark."},
    ]

    page_faqs = faqs.get(slug, default_faqs)

    # Build FAQ schema for this page
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": faq["q"],
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": faq["a"]
                }
            }
            for faq in page_faqs
        ]
    }

    # Generate HTML content
    content_html = f"""
        <div class="seo-sections">
            {base_content["how_it_works"]}
            {base_content["supported_devices"]}
            {base_content["supported_formats"]}
            {base_content["safety"]}
            {base_content["troubleshooting"]}
        </div>

        <div class="faq-section">
            <h2>Frequently Asked Questions</h2>
            {''.join(f'<div class="faq-item"><h4>{faq["q"]}</h4><p>{faq["a"]}</p></div>' for faq in page_faqs)}
        </div>
    """

    return content_html, faq_schema


# Generate related pages for internal linking
def get_related_pages(current_slug):
    """Get related pages for internal linking."""
    all_slugs = list(SEO_PAGES.keys())

    # Simple strategy: show 5 random other pages
    other_slugs = [s for s in all_slugs if s != current_slug]

    # Prioritize core pages
    core_pages = ["download-instagram-reels", "reels-downloader", "instagram-reel-downloader",
                  "hd-reels-downloader", "no-watermark-reels", "free-reels-downloader"]

    related = [s for s in core_pages if s in other_slugs][:5]

    if len(related) < 5:
        # Add more from remaining
        remaining = [s for s in other_slugs if s not in related]
        related.extend(remaining[:5 - len(related)])

    return related


@lru_cache(maxsize=50)
def inject_seo_cached(html, seo_key, slug):
    """Cached SEO injection."""
    seo = SEO_PAGES.get(seo_key, SEO_PAGES["download-instagram-reels"])

    # Build canonical URL
    canonical_url = "https://reelsnag.site/" if slug == "" else f"https://reelsnag.site/{slug}"

    # Inject JS SEO object
    seo_script = f"""
<script id="page-seo">
window.SERVER_SEO = {json.dumps(seo)};
</script>
"""
    html = html.replace("</head>", seo_script + "\n</head>")

    # Replace TITLE
    html = html.replace(
        "<title>Download Instagram Reels Without Watermark (Free) | ReelSnag</title>",
        f"<title>{seo['title']}</title>"
    )

    # Replace CANONICAL
    html = html.replace(
        '<link rel="canonical" href="https://reelsnag.site/" />',
        f'<link rel="canonical" href="{canonical_url}" />'
    )

    # Replace meta description
    desc_pattern = '<meta name="description" content="'
    if desc_pattern in html:
        old_desc_end = html.find('"', html.find(desc_pattern) + len(desc_pattern))
        html = html[:html.find(desc_pattern) + len(desc_pattern)] + seo['description'] + html[old_desc_end:]

    # Replace OG title
    og_title_pattern = '<meta property="og:title" content="'
    if og_title_pattern in html:
        old_og_end = html.find('"', html.find(og_title_pattern) + len(og_title_pattern))
        html = html[:html.find(og_title_pattern) + len(og_title_pattern)] + seo['title'] + html[old_og_end:]

    # Replace OG description
    og_desc_pattern = '<meta property="og:description" content="'
    if og_desc_pattern in html:
        old_og_end = html.find('"', html.find(og_desc_pattern) + len(og_desc_pattern))
        html = html[:html.find(og_desc_pattern) + len(og_desc_pattern)] + seo['description'] + html[old_og_end:]

    return html


# =============================================================================
# ROUTES
# =============================================================================

@app.after_request
def log_request(response):
    """Log requests for observability."""
    if request.path not in ['/favicon.ico', '/static/favicon.PNG']:
        logger.info(f"{request.method} {request.path} - {response.status_code}")
    return response


@app.route('/robots.txt')
def robots():
    """Robots.txt for crawlers."""
    return Response("""User-agent: *
Allow: /

Sitemap: https://reelsnag.site/sitemap.xml
""", mimetype='text/plain')


@app.route('/sitemap.xml')
def sitemap():
    """Dynamic sitemap with all SEO pages."""
    urls = [
        f'  <url><loc>https://reelsnag.site/</loc><priority>1.0</priority><changefreq>daily</changefreq></url>'
    ]

    for slug in SEO_PAGES.keys():
        priority = "0.9" if slug in ["download-instagram-reels", "reels-downloader", "instagram-reel-downloader"] else "0.7"
        urls.append(f'  <url><loc>https://reelsnag.site/{slug}</loc><priority>{priority}</priority><changefreq>weekly</changefreq></url>')

    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap_xml += '\n'.join(urls)
    sitemap_xml += '\n</urlset>'

    return Response(sitemap_xml, mimetype='text/xml')


# HOME ROUTE
@app.route('/')
def index():
    seo = {
        "title": "Download Instagram Reels Without Watermark (Free) | ReelSnag",
        "description": "Download Instagram reels without watermark in HD quality. Free, fast and secure Instagram reel downloader. Paste link and download instantly with ReelSnag.",
        "heading": "Download Instagram Reels",
        "subtitle": "Paste your reel link and download instantly",
        "content": "ReelSnag is a free Instagram reel downloader that allows users to download reels without watermark in HD quality.",
        "keywords": "instagram reels, download reels, reel downloader, no watermark",
    }

    with open("index.html", "r", encoding='utf-8') as f:
        html = f.read()

    return inject_seo_cached(html, 'home', '')


# PROGRAMMATIC SEO ROUTE
@app.route('/<slug>')
def seo_page(slug):
    if slug not in SEO_PAGES:
        # Fallback for unknown slugs - still create a valid page
        seo = {
            "title": f"{slug.replace('-', ' ').title()} | ReelSnag",
            "description": f"Download Instagram reels using {slug.replace('-', ' ')}. Fast, free, and without watermark.",
            "heading": slug.replace('-', ' ').title(),
            "subtitle": "Download Instagram reels instantly",
            "content": f"Use ReelSnag to {slug.replace('-', ' ')} without watermark in HD.",
            "keywords": slug.replace('-', ', '),
        }
    else:
        seo = SEO_PAGES[slug]

    with open("index.html", "r", encoding='utf-8') as f:
        html = f.read()

    response = make_response(inject_seo_cached(html, slug, slug))
    return response


# TRACKING ENDPOINT - Enhanced
@app.route('/track', methods=['POST'])
def track():
    try:
        data = request.get_json(force=True)
        ip = request.remote_addr or 'unknown'

        logger.info(f"TRACK: {data.get('event', 'pageview')} - {data.get('page', '/')} - IP: {ip}")

        # Log conversion events
        if data.get('event') == 'download_success':
            logger.info(f"CONVERSION: Download success - {data.get('page', '/')} - IP: {ip}")
        elif data.get('event') == 'download_error':
            logger.warning(f"CONVERSION: Download error - {data.get('page', '/')} - IP: {ip}")

        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"Track error: {e}")
        return jsonify({"status": "ok"})  # Still return ok to not break frontend


# DOWNLOAD ENDPOINT - Enhanced with rate limiting and better logging
@app.route('/download', methods=['POST'])
def download():
    ip = request.remote_addr or 'unknown'

    # Check rate limit
    if not check_rate_limit(ip):
        logger.warning(f"RATE LIMITED: {ip}")
        return jsonify({'error': 'Too many requests. Please wait a moment.'}), 429

    try:
        data = request.get_json(force=True)
        url = data.get('url', '').strip()
    except Exception as e:
        logger.error(f"Parse error: {e}")
        return jsonify({'error': 'Invalid request'}), 400

    if not url:
        logger.warning(f"Empty URL from {ip}")
        return jsonify({'error': 'Please provide a URL.'}), 400

    # Enhanced URL validation
    try:
        parsed = urlparse(url)
        valid_domains = ['instagram.com', 'www.instagram.com', 'l.instagram.com']
        if not any(d in parsed.netloc for d in valid_domains):
            logger.warning(f"Invalid domain: {parsed.netloc} from {ip}")
            return jsonify({'error': 'Invalid Instagram URL'}), 400

        # Check for valid reel/video path patterns
        valid_patterns = ['/reel/', '/reels/', '/tv/', '/p/']
        if not any(p in parsed.path for p in valid_patterns):
            logger.warning(f"Invalid path pattern: {parsed.path} from {ip}")
            return jsonify({'error': 'This doesn\'t look like a valid reel URL'}), 400

    except Exception as e:
        logger.error(f"URL parse error: {e}")
        return jsonify({'error': 'Invalid URL format'}), 400

    try:
        # Use system temp directory (works on all hosting environments)
        tmp_dir = "/tmp/reelsnag"
        os.makedirs(tmp_dir, exist_ok=True)
        tmp_path = os.path.join(tmp_dir, f"{uuid.uuid4()}")

        ydl_opts = {
            'outtmpl': tmp_path + '.%(ext)s',
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Downloading: {url[:50]}... from {ip}")
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

            # Ensure MP4 extension
            if not file_path.endswith('.mp4'):
                new_path = os.path.splitext(file_path)[0] + '.mp4'
                if os.path.exists(file_path):
                    os.rename(file_path, new_path)
                file_path = new_path

        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return jsonify({'error': 'Download failed'}), 500

        # Schedule cleanup (daemon=True prevents orphan threads on shutdown)
        threading.Thread(target=delete_file_later, args=(file_path,), daemon=True).start()

        logger.info(f"Sending file: {file_path} to {ip}")
        response = send_file(
            file_path,
            as_attachment=True,
            download_name='reelsnag_reel.mp4',
            mimetype='video/mp4'
        )
        response.headers['X-Site-URL'] = request.host_url.rstrip('/')
        return response

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp error: {e}")
        return jsonify({'error': 'Could not download this reel. It may be private or deleted.'}), 500
    except Exception as e:
        logger.error(f"Download error: {e}", exc_info=True)
        return jsonify({'error': 'Failed to download. Please try again.'}), 500


def delete_file_later(path):
    """Delete file after delay with proper error handling."""
    time.sleep(5)  # Increased delay
    try:
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Cleaned up: {path}")
    except Exception as e:
        logger.error(f"Cleanup failed for {path}: {e}")


if __name__ == "__main__":
    logger.info("Starting ReelSnag server...")
    app.run(host="0.0.0.0", port=10000, threaded=True)
