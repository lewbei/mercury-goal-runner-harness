# Thinking Plan: URL Shortener Service

## Architecture
The service consists of two files:
- `requirements.txt` – declares the Python dependencies needed to run the service.
- `app.py` – the Flask application that implements the URL shortener logic.

All code lives in a single package (the repository root) because the goal is small and only requires in‑memory storage. Keeping everything in `app.py` makes the implementation straightforward and avoids unnecessary indirection.

## Design decisions
| Decision | Options Considered | Chosen | Rationale |
|----------|-------------------|--------|-----------|
| **Short code generation** | 1️⃣ Sequential integer IDs encoded in base‑62 (predictable). 2️⃣ Random alphanumeric strings of fixed length (6 chars). | Random alphanumeric strings. | Random codes are harder to guess and do not expose usage statistics. Collisions are extremely unlikely with a 62⁶ space; we still check for collisions before storing. |
| **URL validation** | 1️⃣ Use Python's `urllib.parse` to ensure a scheme and netloc. 2️⃣ Use third‑party `validators` package. | `urllib.parse` only. | Avoids extra dependencies; sufficient for basic validation (must start with http:// or https://). |
| **In‑memory storage** | 1️⃣ Global dictionary. 2️⃣ Flask `g` context. | Global dictionary (`url_map`). | Simple and persists for the life of the process; meets the “in‑memory” requirement. |
| **Error handling** | Return JSON error messages with appropriate HTTP status codes. | JSON with `error` field and status 400 for bad URLs, 404 for missing codes. | Consistent API contract; easy for clients to parse. |
| **Redirect response** | 302 Found (temporary) vs 301 Moved Permanently. | 302 Found. | Allows the short URL to be changed later without caching issues. |

---

## Step 1: requirements.txt

### Why
The first step defines the external libraries needed. Installing dependencies before writing code ensures the environment is reproducible and that the `app.py` can be executed without import errors.

### Design
Only Flask is required. We pin to a recent stable version to avoid breaking changes. No other third‑party packages are needed because URL validation uses the standard library.

### Template
```text
Flask==2.3.2
```

### Validation
```bash
# Install the requirements in a virtual environment
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
# Verify Flask is installed
python -c "import flask; print('Flask version:', flask.__version__)"
```

---

## Step 2: app.py

### Why
`app.py` contains the actual service implementation. It depends on the dependencies declared in `requirements.txt`. This step builds the Flask app, defines the in‑memory store, and implements the two required endpoints.

### Design
- **Global store**: `url_map: dict[str, str] = {}` maps short codes to original URLs.
- **Code generation**: `generate_code()` creates a 6‑character random string from `[a‑zA‑Z0‑9]`. It repeats until a non‑colliding code is found.
- **URL validation**: `is_valid_url(url: str) -> bool` uses `urllib.parse.urlparse` to ensure the URL has a scheme (`http` or `https`) and a network location.
- **POST /shorten**: Accepts JSON `{"url": "..."}`. Validates the URL, generates a code, stores the mapping, and returns `{"short_url": "<base_url>/<code>"}`. Errors return `400` with a JSON error message.
- **GET /<code>**: Looks up the code in `url_map`. If found, redirects (`302`) to the original URL. If not found, returns `404` with a JSON error.
- **Error handling**: All error responses are JSON with an `error` field. Unexpected exceptions are caught by Flask's default handler (which returns HTML); we add a generic `@app.errorhandler(500)` to return JSON for consistency.
- **Running the app**: The script can be executed directly (`python app.py`). It binds to `0.0.0.0` on port `5000` by default.

Edge cases covered:
- Empty or missing `url` field → 400.
- Invalid URL format (no scheme or netloc) → 400.
- Code collision (extremely rare) → regenerated.
- Missing short code in GET → 404.

### Template
```python
# app.py
"""Flask URL Shortener Service.

Provides two endpoints:
- POST /shorten  – accepts JSON {"url": "..."} and returns {"short_url": "..."}
- GET /<code>    – redirects to the original URL or returns 404 if not found.

All data is stored in memory (a global dictionary). The service validates URLs and returns JSON error messages.
"""

import string
import random
from urllib.parse import urlparse
from flask import Flask, request, jsonify, redirect, abort

# ---------------------------------------------------------------------------
# Global in‑memory store
# ---------------------------------------------------------------------------
url_map: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL = "http://localhost:5000"  # Base URL used when constructing short URLs
CODE_LENGTH = 6
CODE_ALPHABET = string.ascii_letters + string.digits

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_valid_url(url: str) -> bool:
    """Return True if *url* appears to be a valid HTTP/HTTPS URL.

    Validation checks:
    - Scheme must be 'http' or 'https'
    - Netloc (domain) must be non‑empty
    - The URL must be parsable by urllib.parse.urlparse
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def generate_code() -> str:
    """Generate a random alphanumeric short code.

    The function ensures the generated code does not already exist in *url_map*.
    In the extremely unlikely event of a collision, it retries until a unique code is produced.
    """
    while True:
        code = ''.join(random.choices(CODE_ALPHABET, k=CODE_LENGTH))
        if code not in url_map:
            return code

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.route('/shorten', methods=['POST'])
def shorten():
    """Create a shortened URL.

    Expected JSON payload: {"url": "..."}
    Returns: {"short_url": "<BASE_URL>/<code>"}
    Errors: 400 with JSON {"error": "..."}
    """
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400
    data = request.get_json()
    url = data.get('url')
    if not isinstance(url, str) or not url.strip():
        return jsonify({"error": "'url' field is required and must be a non‑empty string"}), 400
    if not is_valid_url(url):
        return jsonify({"error": "Invalid URL format; must start with http:// or https://"}), 400
    code = generate_code()
    url_map[code] = url
    short_url = f"{BASE_URL}/{code}"
    return jsonify({"short_url": short_url}), 201

@app.route('/<code>', methods=['GET'])
def redirect_to_original(code: str):
    """Redirect to the original URL for *code*.

    If *code* is unknown, returns 404 with JSON error.
    """
    original_url = url_map.get(code)
    if original_url is None:
        return jsonify({"error": "Short code not found"}), 404
    return redirect(original_url, code=302)

# Ensure JSON error responses for unexpected server errors
@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    # Running on 0.0.0.0 makes the service reachable from other machines (useful for Docker, etc.)
    app.run(host='0.0.0.0', port=5000, debug=False)
```

### Validation
```bash
# 1. Install dependencies (if not already done)
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# 2. Run the Flask app
python app.py &
# The server should start on http://0.0.0.0:5000

# 3. Test POST /shorten with a valid URL
curl -X POST -H "Content-Type: application/json" -d '{"url": "https://example.com"}' http://localhost:5000/shorten
# Expected output: {"short_url": "http://localhost:5000/<code>"}

# 4. Test POST /shorten with an invalid URL
curl -X POST -H "Content-Type: application/json" -d '{"url": "ftp://example.com"}' http://localhost:5000/shorten
# Expected output: {"error": "Invalid URL format; must start with http:// or https://"}

# 5. Test GET /<code> (replace <code> with the code from step 3)
curl -i http://localhost:5000/<code>
# Expected: HTTP/1.1 302 Found with Location header pointing to https://example.com

# 6. Test GET with a non‑existent code
curl -i http://localhost:5000/doesnotexist
# Expected: HTTP/1.1 404 Not Found with JSON error message
```
