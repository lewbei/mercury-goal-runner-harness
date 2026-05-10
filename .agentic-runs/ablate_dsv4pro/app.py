# app.py
"""
Flask URL shortener service.

Provides:
- POST /shorten: Accepts JSON {"url": "<original_url>"} and returns {"code": "<short_code>"}
- GET /<code>: Redirects to the original URL if exists.

In-memory storage is used; data is lost when the process exits.
"""

from __future__ import annotations

import string
import random
import logging
from urllib.parse import urlparse

from flask import Flask, request, jsonify, abort, redirect

# Initialize Flask app
app = Flask(__name__)

# In-memory mapping from short code to original URL
url_map: dict[str, str] = {}

# Configuration
CODE_LENGTH = 6
CODE_CHARSET = string.ascii_letters + string.digits

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _is_valid_url(url: str) -> bool:
    """
    Validate a URL using urllib.parse.

    A valid URL must have a scheme (http or https) and a network location.
    """
    try:
        result = urlparse(url)
        return result.scheme in {"http", "https"} and bool(result.netloc)
    except Exception:
        return False


def _generate_code() -> str:
    """
    Generate a random alphanumeric code of length CODE_LENGTH.
    Collisions are extremely unlikely; in the rare case of a collision,
    generate a new code until a unique one is found.
    """
    while True:
        code = ''.join(random.choices(CODE_CHARSET, k=CODE_LENGTH))
        if code not in url_map:
            return code


@app.route("/shorten", methods=["POST"])
def shorten() -> tuple[dict, int]:
    """
    Create a short code for a given URL.

    Expected JSON payload: {"url": "<original_url>"}
    Returns JSON: {"code": "<short_code>"}
    """
    if not request.is_json:
        abort(400, description="Request body must be JSON")
    data = request.get_json()
    url = data.get("url")
    if not isinstance(url, str) or not url:
        abort(400, description="Missing or empty 'url' field")
    if not _is_valid_url(url):
        abort(400, description="Invalid URL format")
    code = _generate_code()
    url_map[code] = url
    logger.info("Created short code %s for URL %s", code, url)
    return jsonify({"code": code}), 201


@app.route("/<code>", methods=["GET"])
def redirect_to_url(code: str):
    """
    Redirect to the original URL associated with the given short code.
    """
    url = url_map.get(code)
    if url is None:
        abort(404, description="Short code not found")
    logger.info("Redirecting code %s to URL %s", code, url)
    return redirect(url, code=302)


# Optional health check endpoint
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    # Run the Flask development server
    app.run(host="0.0.0.0", port=5000, debug=False)
