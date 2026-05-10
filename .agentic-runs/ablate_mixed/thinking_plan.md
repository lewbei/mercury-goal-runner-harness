# Thinking Plan: URL Shortener Service

## Architecture
The service consists of a single Flask application (`app.py`) that holds an **in‑memory dictionary** mapping short codes to original URLs. A tiny **base‑62 counter** generates unique, URL‑friendly short codes. The application exposes two HTTP endpoints:
1. `POST /shorten` – accepts JSON `{"url": "<original>"}` validates the URL, creates a short code, stores it, and returns `{"short_url": "<host>/<code>"}`.
2. `GET /<code>` – looks up the code and redirects (`302`) to the original URL, or returns `404` if the code does not exist.

All dependencies are listed in `requirements.txt`. No external storage or background workers are required, keeping the implementation lightweight and easy to run locally.

## Design decisions
| Decision | Alternatives considered | Chosen option | Rationale |
|----------|--------------------------|---------------|-----------|
| **Storage** | Persistent DB (SQLite, Redis) vs. In‑memory dict | In‑memory dict | The goal only requires a simple, transient service; persistence adds unnecessary complexity and external dependencies. |
| **Short code generation** | Random alphanumeric string (e.g., `secrets.token_urlsafe`) vs. Incremental counter encoded in base‑62 | Incremental base‑62 counter | Guarantees uniqueness without collisions, produces short URLs, and is deterministic (easy to test). Random strings would need collision checks. |
| **Web framework** | Flask vs. FastAPI vs. Django | Flask | Minimalistic, already familiar, and sufficient for two endpoints. FastAPI adds async overhead; Django is overkill. |
| **URL validation** | Regex pattern vs. `urllib.parse` | `urllib.parse` validation | Using the standard library avoids extra dependencies and correctly handles scheme and netloc checks. |
| **Error handling** | Custom error pages vs. JSON error responses | JSON error responses with proper HTTP status codes (400/404) | Aligns with typical API design and satisfies the contract's criteria. |

The chosen design balances simplicity, testability, and compliance with the contract.

---

## Step 1: requirements.txt

### Why
The first step defines the third‑party packages needed to run the Flask application. Installing dependencies up front ensures the environment is ready before any code execution.

### Design
Only Flask is required. Pinning a recent stable version avoids compatibility surprises while keeping the file minimal.

### Template
```text
Flask>=2.3.0
```

### Validation
```bash
# Install dependencies in a virtual environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Verify Flask is installed
python -c "import flask; print('Flask version:', flask.__version__)"
```

---

## Step 2: app.py

### Why
This step implements the core functionality of the URL shortener, fulfilling all success criteria: running the app, handling POST/GET, and proper error responses.

### Design
- **Global state**: `url_map` (dict) stores `code -> original_url`. `counter` (itertools.count) provides a monotonically increasing integer for code generation.
- **Base‑62 encoding**: `encode_base62(num)` converts an integer to a short alphanumeric string using digits, lowercase, and uppercase letters.
- **URL validation**: `is_valid_url(url)` parses the URL and ensures a scheme of `http` or `https` and a non‑empty network location.
- **Endpoints**:
  - `POST /shorten` validates JSON payload, checks the URL, generates a code, stores the mapping, and returns the full short URL.
  - `GET /<code>` looks up the code; on success, issues a `302` redirect; otherwise returns `404`.
- **Error handling**: Custom error handlers return JSON with an `error` field and appropriate HTTP status.
- **Thread safety**: The default Flask development server is single‑threaded; for multi‑threaded deployments a lock could be added, but is omitted for brevity as the contract does not require concurrency guarantees.
- **Entry point**: `if __name__ == "__main__":` runs the app on host `0.0.0.0` port `5000`.

All functions include type hints, docstrings, and explicit error handling.

### Template
```python
# app.py
"""Flask URL shortener service.

Provides two endpoints:
- POST /shorten  – create a short URL for a given original URL.
- GET /<code>    – redirect to the original URL.

The service stores mappings in memory and uses a base‑62 counter for short codes.
"""

import itertools
import string
from urllib.parse import urlparse

from flask import Flask, jsonify, request, redirect, abort, make_response

# ---------------------------------------------------------------------------
# Configuration & global state
# ---------------------------------------------------------------------------

app = Flask(__name__)

# In‑memory storage: short code -> original URL
url_map: dict[str, str] = {}

# Counter for generating unique IDs (starts at 1 to avoid empty string)
counter = itertools.count(1)

# Characters for base‑62 encoding (0‑9, a‑z, A‑Z)
BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

\ encode_base62(num: int) -> str:
    """Encode a non‑negative integer to a base‑62 string.

    Args:
        num: Integer to encode (must be >= 0).

    Returns:
        A base‑62 representation using characters 0‑9, a‑z, A‑Z.
    """
    if num < 0:
        raise ValueError("Base62 encoding only supports non‑negative integers")
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
    runs single‑threaded. For a production multi‑process setup a lock would be
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
        400 – if JSON is malformed or URL is invalid.
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
```

### Validation
```bash
# 1. Install dependencies (if not already done)
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Run the Flask app
python app.py &
# The app will start on http://127.0.0.1:5000

# 3. Test POST /shorten with a valid URL
curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}' | python -m json.tool

# Expected output: {"short_url": "http://127.0.0.1:5000/<code>"}

# 4. Test GET /<code> (replace <code> with the one returned above)
curl -i http://127.0.0.1:5000/<code>
# Expected: HTTP/1.1 302 FOUND with Location header pointing to https://example.com

# 5. Test invalid URL handling
curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "not-a-url"}' | python -m json.tool
# Expected: {"error": "Invalid URL supplied"} with HTTP 400

# 6. Test missing code handling
curl -i http://127.0.0.1:5000/nonexistent
# Expected: HTTP/1.1 404 NOT FOUND with JSON error body

# 7. Stop the server (kill background process)
kill %1
```
