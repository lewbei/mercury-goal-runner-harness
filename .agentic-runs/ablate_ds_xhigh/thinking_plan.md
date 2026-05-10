# Thinking Plan: URL Shortener Service

## Architecture
We will build a minimal Flask application that stores URL mappings in memory using a Python dictionary. The service consists of two files:

- `requirements.txt` – declares the Python dependencies (Flask). Keeping dependencies explicit makes the environment reproducible.
- `app.py` – contains the Flask app with the required endpoints, URL validation logic, and in‑memory storage.

The architecture is deliberately flat because the goal is a simple, single‑process service. No additional modules or packages are needed, which keeps the code easy to understand and test. All functionality lives in `app.py`, and the in‑memory store is a module‑level dictionary, which satisfies the “in‑memory” requirement without persistence.

## Design decisions

| Decision | Alternatives Considered | Chosen | Rationale |
|----------|------------------------|--------|-----------|
| **Web framework** | Flask, FastAPI, Django | **Flask** | Flask is lightweight, has minimal boilerplate, and is sufficient for two endpoints. FastAPI would require async handling and extra dependencies; Django is overkill.
| **Storage** | In‑memory dict, SQLite, Redis | **In‑memory dict** | The contract explicitly asks for in‑memory storage. A dict provides O(1) look‑ups and is simple to serialize for tests if needed.
| **Short code generation** | Random UUID, incremental integer, Base62 of random bytes | **Base62 of 6 random bytes** | Generates short, URL‑friendly strings (~8 characters) with negligible collision risk for the expected usage. UUIDs are too long; incremental integers expose usage patterns.
| **URL validation** | `validators` package, custom regex, `urllib.parse` | **`urllib.parse` + simple scheme check** | Avoids extra dependencies; sufficient to catch malformed URLs (missing scheme or netloc). The `validators` package would add a dependency for minimal benefit.
| **Error handling** | Return JSON error messages, plain text, HTML | **JSON error messages** | Aligns with typical API design and makes automated testing easier. The contract expects HTTP 400/404 responses; JSON payloads provide clear error details.
| **Redirect response** | 301 Moved Permanently, 302 Found, 307 Temporary Redirect | **302 Found** | Standard for short URL services, indicating a temporary redirect. 301 could be cached aggressively, which is undesirable for a mutable in‑memory store.

All decisions are documented to satisfy the **question‑contract** skill (verifying success criteria) and the **design‑options** skill (showing alternatives). The **research‑pack** skill informs us that we target Python 3.10+ and only need Flask as an external library.

---

## Step 1: requirements.txt

### Why
The first step is to declare dependencies. Installing the correct packages is a prerequisite for running the Flask app and for reproducible environments. This step establishes the environment that the subsequent code will rely on.

### Design
`requirements.txt` will list the exact packages needed. We keep it minimal: Flask (the web framework). No version pinning is required for this prototype, but we could optionally specify `Flask>=2.0` to ensure modern features.

### Template
```text
# requirements.txt
Flask
```

### Validation
```bash
# Install dependencies in a virtual environment
python -m venv venv && source venv/Scripts/activate && pip install -r requirements.txt
# Verify Flask is installed
python -c "import flask; print('Flask version:', flask.__version__)"
```

---

## Step 2: app.py

### Why
`app.py` implements the core functionality: the Flask application, URL validation, short code generation, in‑memory storage, and the required endpoints. This step depends on the environment set up in Step 1.

### Design
- **In‑memory store**: a module‑level dict `url_map: dict[str, str] = {}` mapping short codes to original URLs.
- **Short code generation**: a helper `_generate_code()` that returns a 8‑character Base62 string using `secrets.choice` over the alphabet `0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ`.
- **URL validation**: a helper `_is_valid_url(url: str) -> bool` that uses `urllib.parse.urlparse` to ensure the scheme is `http` or `https` and that a network location (`netloc`) exists.
- **POST /shorten**: expects JSON `{ "url": "<original>" }`. Returns `{ "code": "<short>" }` with status 201 on success, or `{ "error": "Invalid URL" }` with status 400.
- **GET /<code>**: looks up the code in `url_map`. If found, returns a 302 redirect to the original URL. If not found, returns `{ "error": "Code not found" }` with status 404.
- **Error handling**: all error responses are JSON with a clear `error` field. Flask's `abort` is used with custom error handlers to enforce JSON output.
- **Thread safety**: Flask's built‑in development server runs single‑threaded by default; for production we would need synchronization, but it is out of scope for this prototype.
- **Logging**: simple `print` statements for debugging (optional).

### Template
```python
# app.py
"""Flask URL shortener service.

Endpoints:
- POST /shorten  -> JSON {"code": "<short>"}
- GET /<code>    -> 302 redirect or 404 JSON error

The service stores mappings in memory using a dictionary.
"""

import secrets
import string
from urllib.parse import urlparse

from flask import Flask, request, jsonify, abort, redirect

app = Flask(__name__)

# In‑memory storage: short code -> original URL
url_map: dict[str, str] = {}

# Alphabet for Base62 encoding
_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase
_CODE_LENGTH = 8


def _generate_code() -> str:
    """Generate a random Base62 code of length `_CODE_LENGTH`.

    The function checks for collisions and retries up to 5 times.
    """
    for _ in range(5):
        code = ''.join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))
        if code not in url_map:
            return code
    # In the extremely unlikely event of repeated collisions, raise an error
    raise RuntimeError('Failed to generate unique short code after several attempts')


def _is_valid_url(url: str) -> bool:
    """Return True if `url` appears to be a valid HTTP/HTTPS URL.

    Validation criteria:
    - Scheme is 'http' or 'https'
    - Netloc (domain) is non‑empty
    - The URL can be parsed without raising
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)
    except Exception:
        return False

# Custom error handlers to ensure JSON responses
@app.errorhandler(400)
def bad_request(error):
    response = jsonify({'error': str(error.description) if error.description else 'Bad Request'})
    response.status_code = 400
    return response

@app.errorhandler(404)
def not_found(error):
    response = jsonify({'error': str(error.description) if error.description else 'Not Found'})
    response.status_code = 404
    return response

@app.route('/shorten', methods=['POST'])
def shorten():
    """Create a short code for a given URL.

    Expected JSON payload: {"url": "<original_url>"}
    Returns: {"code": "<short_code>"} with HTTP 201 on success.
    Returns HTTP 400 with JSON error if URL is missing or invalid.
    """
    if not request.is_json:
        abort(400, description='Request body must be JSON')
    data = request.get_json()
    url = data.get('url')
    if not isinstance(url, str) or not _is_valid_url(url):
        abort(400, description='Invalid URL')
    code = _generate_code()
    url_map[code] = url
    return jsonify({'code': code}), 201

@app.route('/<code>', methods=['GET'])
def redirect_to_url(code: str):
    """Redirect to the original URL for a given short code.

    If the code does not exist, returns HTTP 404 with JSON error.
    """
    original = url_map.get(code)
    if original is None:
        abort(404, description='Code not found')
    return redirect(original, code=302)

if __name__ == '__main__':
    # Run the development server; in production use a proper WSGI server.
    app.run(host='0.0.0.0', port=5000, debug=True)
```

### Validation
```bash
# 1. Install dependencies (if not already done)
python -m venv venv && source venv/Scripts/activate && pip install -r requirements.txt

# 2. Run the Flask app
python app.py &
# The app should start on http://0.0.0.0:5000

# 3. Test POST /shorten with a valid URL
curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}' | jq .
# Expected output: {"code": "<8‑char string>"}

# 4. Test POST /shorten with an invalid URL
curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "not a url"}' | jq .
# Expected HTTP status 400 and JSON error

# 5. Test GET redirect (replace <code> with the code from step 3)
CODE=$(curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}' | jq -r .code)

 -i http://127.0.0.1:5000/$CODE
# Expected HTTP 302 with Location: https://example.com

# 6. Test GET with unknown code
curl -i http://127.0.0.1:5000/unknowncode
# Expected HTTP 404 with JSON error
```
