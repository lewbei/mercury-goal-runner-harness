# Thinking Plan: URL Shortener

## Architecture
The solution is a single Flask application (`app.py`) that stores URL mappings in an in‑memory dictionary. The dictionary maps short codes (generated via a deterministic Base62 encoding of an incrementing integer) to the original URLs. A minimal `requirements.txt` file declares the Flask dependency. This architecture satisfies the goal’s constraints (no external storage, simple deployment) while keeping the codebase small and testable.

## Design decisions
- **Short code generation**: We considered two options: (A) random alphanumeric strings, (B) deterministic Base62 encoding of an integer counter. Random strings avoid predictability but require collision checking; Base62 with a counter guarantees uniqueness without extra checks and yields short, human‑readable codes. We chose **Option B** for simplicity and determinism.
- **URL validation**: Options were (A) regex validation, (B) using `urllib.parse` to check scheme and netloc. Regex is error‑prone; `urllib.parse` is part of the standard library and sufficient for basic validation. We chose **Option B**.
- **Error handling**: Flask’s `abort` function cleanly returns HTTP error codes. We will return `400 Bad Request` for malformed input and `404 Not Found` when a code does not exist.
- **In‑memory storage**: The requirement explicitly calls for in‑memory storage, so we use a global dictionary and an integer counter. Persistence across restarts is not needed.
- **Testing strategy**: Validation steps use `curl` to exercise the API endpoints, confirming JSON responses, redirects, and error codes.

---

## Step 1: requirements.txt

### Why
The Flask framework is required to run the web service. Installing dependencies first ensures the environment is ready before the application code is executed.

### Design
Only Flask is needed. We pin a recent stable version to avoid breaking changes.

### Template
```text
Flask==2.3.2
```

### Validation
```bash
# Install dependencies
pip install -r requirements.txt
# Verify Flask is installed
pip show Flask
```

---

## Step 2: app.py

### Why
This file implements the core functionality: the Flask routes, URL validation, short‑code generation, and in‑memory storage. It depends on the Flask package installed in Step 1.

### Design
- **Global state**: `url_map` (dict) stores `code -> original_url`. `counter` (int) tracks the next ID for encoding.
- **Base62 encoding**: `encode_base62(num)` converts an integer to a short alphanumeric string using digits, lowercase, and uppercase letters.
- **URL validation**: `is_valid_url(url)` checks that the URL has a scheme (`http` or `https`) and a network location.
- **POST /shorten**: Accepts JSON `{"url": "..."}`. Validates JSON structure and URL format, generates a short code, stores the mapping, and returns `{"code": "...", "short_url": "http://<host>/<code>"}` with status 201.
- **GET /<code>**: Looks up the code; if found, issues a `302` redirect to the original URL; otherwise returns `404`.
- **Error handling**: Uses `abort(400, description=...)` for bad input and `abort(404)` for missing codes. All error responses are JSON‑formatted via a Flask error handler.
- **Running the app**: The `if __name__ == "__main__":` block starts Flask on `0.0.0.0:5000` for easy testing.

### Template
```python
# app.py
"""A minimal in‑memory URL shortener built with Flask.

Endpoints:
- POST /shorten – JSON body {"url": "<original_url>"}
    Returns JSON {"code": "<short_code>", "short_url": "http://<host>/<short_code>"}
- GET /<code> – redirects (302) to the original URL or 404 if not found.

Error handling:
- 400 Bad Request for malformed JSON or invalid URLs.
- 404 Not Found for unknown short codes.
"""

import string
import urllib.parse
from flask import Flask, request, jsonify, redirect, abort, make_response

app = Flask(__name__)

# In‑memory storage
url_map: dict[str, str] = {}
counter: int = 1  # start at 1 to avoid empty string in Base62

# Base62 character set: 0‑9, a‑z, A‑Z
BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase
BASE62_BASE = len(BASE62_ALPHABET)


def encode_base62(num: int) -> str:
    """Encode a non‑negative integer to a Base62 string.

    Args:
        num: Integer to encode (must be >= 0).

    Returns:
        Base62 representation without leading zeros.
    """
    if num < 0:
        raise ValueError("Base62 encoding only supports non‑negative integers")
    if num == 0:
        return BASE62_ALPHABET[0]
    chars = []
    while num > 0:
        num, rem = divmod(num, BASE62_BASE)
        chars.append(BASE62_ALPHABET[rem])
    return ''.join(reversed(chars))


def is_valid_url(url: str) -> bool:
    """Validate that a URL has a proper scheme and network location.

    This is a lightweight check sufficient for the demo.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def generate_code() -> str:
    """Generate a unique short code using the global counter.

    The counter is incremented atomically (single‑threaded Flask dev server).
    """
    global counter
    code = encode_base62(counter)
    counter += 1
    return code

@app.errorhandler(400)
def handle_400(error):
    """Return JSON for 400 errors."""
    response = jsonify({"error": error.description if hasattr(error, "description") else "Bad Request"})
    response.status_code = 400
    return response

@app.errorhandler(404)
def handle_404(error):
    """Return JSON for 404 errors."""
    response = jsonify({"error": "Not found"})
    response.status_code = 404
    return response

@app.route('/shorten', methods=['POST'])
def shorten():
    """Create a short URL for a given original URL.

    Expected JSON payload: {"url": "<original_url>"}
    Returns JSON: {"code": "<short_code>", "short_url": "http://<host>/<short_code>"}
    """
    if not request.is_json:
        abort(400, description="Request body must be JSON")
    data = request.get_json()
    if not isinstance(data, dict) or 'url' not in data:
        abort(400, description="Missing 'url' field in JSON payload")
    original_url = data['url']
    if not isinstance(original_url, str) or not is_valid_url(original_url):
        abort(400, description="Invalid URL supplied")
    code = generate_code()
    url_map[code] = original_url
    # Build absolute short URL using request.host_url
    short_url = urllib.parse.urljoin(request.host_url, code)
    return jsonify({"code": code, "short_url": short_url}), 201

@app.route('/<code>', methods=['GET'])
def redirect_to_original(code: str):
    """Redirect to the original URL for a given short code.

    If the code does not exist, returns 404.
    """
    original_url = url_map.get(code)
    if original_url is None:
        abort(404)
    return redirect(original_url, code=302)

if __name__ == '__main__':
    # Enable debug mode for development; in production, use a proper WSGI server.
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### Validation
```bash
# Install dependencies (if not already done)
pip install -r requirements.txt

# Run the Flask app
python app.py &
# Give the server a moment to start
sleep 2

# Test POST /shorten with a valid URL
curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}' | jq .
# Expected: JSON with "code" and "short_url"

# Test GET redirect using the returned code (replace <code> with actual output)
CODE=$(curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}' | jq -r .code)

 -I http://127.0.0.1:5000/$CODE
# Expected: HTTP/1.1 302 Found with Location: https://example.com

# Test POST with bad URL
curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "not-a-url"}' -w "%{http_code}\n"
# Expected: 400 Bad Request

# Test GET with unknown code
curl -I http://127.0.0.1:5000/unknowncode
# Expected: 404 Not Found

# Stop the Flask server (kill background job)
kill %1
```

---
