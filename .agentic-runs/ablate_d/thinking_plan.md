# Thinking Plan: URL Shortener

## Architecture
The project consists of two top‑level files:
- **requirements.txt** – declares the Python dependencies (Flask). Keeping dependencies separate makes the environment reproducible and satisfies the `final_outputs` contract.
- **app.py** – the Flask web application that implements the URL‑shortening service. All logic lives in a single module because the service is deliberately minimal (in‑memory storage, no persistence layer). This keeps the codebase easy to understand and test while still meeting the required endpoints and error handling.

The Flask app will expose two routes:
1. `POST /shorten` – accepts a JSON payload `{ "url": "<original>" }`, validates the URL, generates a short code, stores the mapping in a Python dictionary, and returns `{ "code": "<code>" }`.
2. `GET /<code>` – looks up the code in the dictionary and redirects to the original URL with a 302 status. If the code does not exist, a 404 response is returned.

All data is stored in‑memory (`url_map` dict) and a simple integer counter (`next_id`) is used to generate unique short codes via Base‑62 encoding. This guarantees uniqueness without the risk of collisions that a random generator would have.

## Design decisions

| Aspect | Options Considered | Chosen | Rationale |
|--------|-------------------|--------|-----------|
| **Code generation** | Random alphanumeric string (e.g., `secrets.token_urlsafe`) vs incremental integer encoded in Base‑62 | Incremental integer + Base‑62 | Guarantees uniqueness without needing to check for collisions; deterministic and easy to test. Random strings could collide and require additional checks. |
| **URL validation** | Regex validation vs `urllib.parse` parsing | `urllib.parse` parsing and scheme/netloc check | `urllib.parse` is part of the standard library, reliable, and avoids over‑complicated regexes. |
| **Error handling** | Return plain text messages vs JSON error bodies | JSON error bodies with appropriate HTTP status codes (400, 404) | Consistent with RESTful API practices; easier for clients to parse. |
| **Dependency management** | Pin exact Flask version vs allow any recent version | `Flask>=2.0` (no exact pin) | Gives flexibility while ensuring required features (e.g., `abort`, `redirect`). |
| **Project layout** | Multi‑module package vs single file | Single file (`app.py`) | The goal is simple; a single module reduces boilerplate and satisfies the `final_outputs` list. |

---

## Step 1: requirements.txt

### Why
The first step declares the Python packages needed to run the Flask application. Having a `requirements.txt` file allows the implementer (and any CI system) to install dependencies in a reproducible way before running the code.

### Design
Only Flask is required. We specify a minimum version of 2.0 to ensure the `abort` and `redirect` helpers are available. No other third‑party libraries are needed because URL validation uses the standard library.

### Template
```text
# requirements.txt
Flask>=2.0
```

### Validation
Run the following command in the project root and verify that Flask is installed without errors:

```bash
pip install -r requirements.txt
```

If the command succeeds, the environment is ready for the Flask app.

---

## Step 2: app.py

### Why
`app.py` contains the actual implementation of the URL shortener service. It depends on the dependencies defined in `requirements.txt` and provides the two required endpoints with proper error handling.

### Design
- **Imports**: `Flask`, `request`, `abort`, `redirect` from Flask; `urllib.parse` for URL validation; `string` and `typing` for helper functions.
- **Global state**: `url_map: dict[str, str]` stores the mapping from short code to original URL. `next_id: int` is an auto‑incrementing counter used for code generation.
- **Base‑62 encoding**: A helper `encode_base62(num: int) -> str` converts an integer to a short alphanumeric string using digits, lowercase and uppercase letters.
- **URL validation**: `is_valid_url(url: str) -> bool` checks that the URL has a scheme (`http` or `https`) and a network location.
- **POST /shorten**: Expects JSON with a `url` field. If missing or invalid, abort with 400 and a JSON error message. Generates a new code, stores the mapping, and returns JSON `{ "code": "<code>" }`.
- **GET /<code>**: Retrieves the original URL from `url_map`. If not found, abort with 404 and a JSON error. Otherwise, redirects with a 302 status.
- **Error handlers**: Custom JSON error responses for 400 and 404 to satisfy the contract.
- **Running the app**: The script can be executed directly (`python app.py`) which runs Flask's built‑in development server on `http://127.0.0.1:5000`.

All functions include docstrings, type hints, and explicit error handling. Edge cases such as missing JSON payload, missing `url` key, malformed URLs, and unknown short codes are covered.

### Template
```python
# app.py
"""Flask URL shortener service.

Provides:
- POST /shorten – create a short code for a given URL.
- GET /<code> – redirect to the original URL.

All data is stored in‑memory. Errors are returned as JSON with appropriate HTTP status codes.
"""

from __future__ import annotations

import string
from typing import Dict
from urllib.parse import urlparse

from flask import Flask, request, abort, redirect, jsonify

# ---------------------------------------------------------------------------
# Global in‑memory storage and counter
# ---------------------------------------------------------------------------
url_map: Dict[str, str] = {}
next_id: int = 1  # start at 1 to avoid empty string encoding

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

\ encode_base62(num: int) -> str:
    """Encode a non‑negative integer to a Base‑62 string.

    Args:
        num: Integer to encode (must be >= 0).

    Returns:
        Base‑62 representation (e.g., 0 -> "0", 61 -> "Z").
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

    Args:
        url: URL string to validate.

    Returns:
        True if URL looks valid, False otherwise.
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Flask app setup
# ---------------------------------------------------------------------------
app = Flask(__name__)

# ---------------------------------------------------------------------------
# Error handlers returning JSON
# ---------------------------------------------------------------------------
@app.errorhandler(400)
def bad_request(error):
    """Return a JSON 400 response."""
    response = jsonify({"error": "Bad Request", "message": error.description if hasattr(error, "description") else "Invalid request"})
    response.status_code = 400
    return response

@app.errorhandler(404)
def not_found(error):
    """Return a JSON 404 response."""
    response = jsonify({"error": "Not Found", "message": error.description if hasattr(error, "description") else "Resource not found"})
    response.status_code = 404
    return response

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/shorten', methods=['POST'])
def shorten_url():
    """Create a short code for a given URL.

    Expects JSON payload: {"url": "<original_url>"}
    Returns JSON: {"code": "<short_code>"}
    """
    if not request.is_json:
        abort(400, description="Request body must be JSON")
    data = request.get_json()
    if not isinstance(data, dict) or 'url' not in data:
        abort(400, description="JSON must contain a 'url' field")
    original_url = data['url']
    if not isinstance(original_url, str) or not is_valid_url(original_url):
        abort(400, description="Provided URL is not valid")

    global next_id
    code = encode_base62(next_id)
    next_id += 1
    url_map[code] = original_url
    return jsonify({"code": code}), 201

@app.route('/<code>', methods=['GET'])
def redirect_to_url(code: str):
    """Redirect to the original URL for the given short code.

    If the code does not exist, a 404 JSON error is returned.
    """
    original = url_map.get(code)
    if original is None:
        abort(404, description=f"Short code '{code}' not found")
    return redirect(original, code=302)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    # Enable debug mode only when explicitly set via environment variable
    app.run(host='127.0.0.1', port=5000, debug=False)
```

### Validation
1. **Start the server**
   ```bash
   python app.py
   ```
   The console should show Flask listening on `http://127.0.0.1:5000`.
2. **Test POST /shorten with a valid URL**
   ```bash
   curl -i -X POST http://127.0.0.1:5000/shorten \
        -H "Content-Type: application/json" \
        -d '{"url": "https://example.com"}'
   ```
   Expected response: HTTP 201 with JSON `{"code": "0"}` (or another short code).
3. **Test POST /shorten with an invalid URL**
   ```bash
   curl -i -X POST http://127.0.0.1:5000/shorten \
        -H "Content-Type: application/json" \
        -d '{"url": "not-a-url"}'
   ```
   Expected response: HTTP 400 with a JSON error message.
4. **Test GET /<code> for an existing code**
   Assuming the previous POST returned code `0`:
   ```bash
   curl -i http://127.0.0.1:5000/0
   ```
   Expected response: HTTP 302 with `Location: https://example.com`.
5. **Test GET /<code> for a missing code**
   ```bash
   curl -i http://127.0.0.1:5000/doesnotexist
   ```
   Expected response: HTTP 404 with a JSON error message.

If all commands behave as described, the implementation satisfies the goal contract.

---
