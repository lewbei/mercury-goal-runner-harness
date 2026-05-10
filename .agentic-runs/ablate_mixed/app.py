# app.py
"""Flask URL shortener service.

Provides two endpoints:
- POST /shorten  – create a short URL for a given original URL.
- GET /<code>    – redirect to the original URL.

The service stores mappings in memory and uses a base-62 counter for short codes.
"""

import itertools
import string
from urllib.parse import urlparse

from flask import Flask, jsonify, request, redirect, abort, make_response

# ---------------------------------------------------------------------------
# Configuration & global state
# ---------------------------------------------------------------------------

app = Flask(__name__)

# In-memory storage: short code -> original URL
url_map: dict[str, str] = {}

# Counter for generating unique IDs (starts at 1 to avoid empty string)
counter = itertools.count(1)

# Characters for base-62 encoding (0-9, a-z, A-Z)
BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def encode_base62(num: int) -> str:
    """Encode a non-negative integer to a base-62 string.

    Args:
        num: Integer to encode (must be >= 0).

    Returns:
        A base-62 representation using characters 0-9, a-z, A-Z.
    """
    if num < 0:
        raise ValueError("Base62 encoding only supports non-negative integers")
    if num == 0:
        return BASE62_ALPHABET[0]
    chars = []
    base = len(BASE62_ALPHABET)
    while num:
        num, rem = divmod(num, base)
        chars.append(BASE62_ALPHABET[rem])
    return ''.join(reversed(chars))


def is_valid_url(url: str) -> bool:
    """Validate that a URL has a proper scheme and network location.

    Accepts only http and https URLs.
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def generate_short_code() -> str:
    """Generate a new unique short code using the global counter.

    The function is deliberately simple because the Flask development server
    runs single-threaded. For a production multi-process setup a lock would be
    required.
    """
    next_id = next(counter)
    return encode_base62(next_id)

# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(error):
    """Return JSON for 400 Bad Request errors."""
    response = jsonify({"error": str(error.description) if error.description else "Bad request"})
    response.status_code = 400
    return response

@app.errorhandler(404)
def not_found(error):
    """Return JSON for 404 Not Found errors."""
    response = jsonify({"error": "Short code not found"})
    response.status_code = 404
    return response

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/shorten', methods=['POST'])
def shorten_url():
    """Create a short URL for a provided original URL.

    Expected JSON payload: {"url": "<original_url>"}
    Returns: {"short_url": "<host>/<code>"}
    Raises:
        400 - if JSON is malformed or URL is invalid.
    """
    if not request.is_json:
        abort(400, description="Request payload must be JSON")
    data = request.get_json()
    original_url = data.get('url')
    if not isinstance(original_url, str):
        abort(400, description="'url' field must be a string")
    if not is_valid_url(original_url):
        abort(400, description="Invalid URL supplied")
    # Generate a unique short code and store mapping
    code = generate_short_code()
    url_map[code] = original_url
    # Build the full short URL using the request's host URL
    short_url = f"{request.host_url.rstrip('/')}/{code}"
    return jsonify({"short_url": short_url})

@app.route('/<code>', methods=['GET'])
def redirect_short(code: str):
    """Redirect to the original URL associated with *code*.

    If the code does not exist, a 404 JSON response is returned.
    """
    original = url_map.get(code)
    if original is None:
        abort(404)
    return redirect(original, code=302)

# ---------------------------------------------------------------------------
# Application entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    # Running on all interfaces makes the service reachable from Docker or VM.
    app.run(host='0.0.0.0', port=5000, debug=False)
