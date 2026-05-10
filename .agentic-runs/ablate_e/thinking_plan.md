# Thinking Plan: URL shortener

## Architecture
The solution consists of two files:

1. **requirements.txt** – declares the Python dependencies needed to run the Flask application. Keeping dependencies separate makes the environment reproducible and satisfies the `final_outputs` contract.
2. **app.py** – the Flask web service that implements the URL shortener. It contains the in‑memory store, request handling, URL validation, code generation, and error handling. All logic lives in a single module to keep the project minimal and easy to understand, matching the `final_outputs` list.

The in‑memory store is a thread‑safe dictionary (`dict`) protected by a `threading.Lock`. This satisfies the requirement for an in‑memory solution while being safe for concurrent requests.

## Design decisions

### Storage
- **Option A – In‑memory dict (chosen)**: Simple, fast, no external services. Works for the demo and satisfies the contract.
- **Option B – SQLite**: Provides persistence but adds complexity and disk I/O, unnecessary for the minimal requirement.
- **Option C – Redis**: External service, overkill for a simple demo.

*Why chosen*: The contract explicitly states “in‑memory”. A dict is the most straightforward implementation and meets the performance expectations.

### URL validation
- **Option A – `validators.url` library (chosen)**: Robust, well‑tested, handles many edge cases (schemes, IPs, Unicode).
- **Option B – Hand‑rolled regex**: Error‑prone, hard to maintain, may miss valid URLs.
- **Option C – `urllib.parse`**: Requires additional logic to check scheme and netloc.

*Why chosen*: Using a dedicated library reduces bugs and keeps the code concise.

### Short code generation
- **Option A – Random Base62 string of length 6 (chosen)**: Provides ~56 billion possible codes, low collision probability for a demo.
- **Option B – Incremental integer encoded in Base62**: Simpler to guarantee uniqueness but leaks the number of URLs created.
- **Option C – UUID**: Too long for a short URL.

*Why chosen*: Random generation is easy, stateless, and sufficient for the expected usage. Collisions are handled by retrying generation.

### Error handling
- Return **400 Bad Request** for missing or invalid `url` fields.
- Return **404 Not Found** for unknown short codes.
- Use Flask’s `abort` with custom error messages to make responses clear.

---

## Step 1: requirements.txt

### Why
The first step establishes the environment. Installing the correct libraries is required before the Flask app can run, and it allows the implementer to verify the setup early.

### Design
Only two dependencies are needed:
- `Flask` – the web framework.
- `validators` – for robust URL validation.
Both are pinned to a minimum version that is compatible with Python 3.9+ (the default on the platform).

### Template
```text
Flask>=2.0
validators>=0.20
```

### Validation
```bash
# Install dependencies
pip install -r requirements.txt
# Verify installation
pip list | grep -E "Flask|validators"
```

---

## Step 2: app.py

### Why
`app.py` is the core of the solution. It implements the POST `/shorten` endpoint, the GET `/<code>` redirect, and all required error handling. It depends on the packages defined in Step 1.

### Design
- **Global store**: `url_map: dict[str, str] = {}` protected by `store_lock = threading.Lock()`.
- **Code generation**: `generate_code()` creates a random 6‑character Base62 string and retries on collision.
- **POST /shorten**:
  - Expects JSON `{ "url": "..." }`.
  - Validates presence and format using `validators.url`.
  - Returns `{"code": "<code>"}` with status 201.
  - Returns 400 with a JSON error message on failure.
- **GET /<code>**:
  - Looks up the code; if found, redirects (302) to the original URL.
  - If not found, aborts with 404 and JSON error.
- **Error handlers**: Custom JSON responses for 400 and 404 to satisfy the contract.
- **Thread safety**: All mutations/reads of `url_map` occur inside `store_lock`.
- **Running**: `if __name__ == "__main__": app.run(host="0.0.0.0", port=5000, debug=False)`.

### Template
```python
# app.py
"""Flask URL shortener – in‑memory implementation.

Endpoints:
- POST /shorten  – JSON body {"url": "<original_url>"} → {"code": "<short_code>"}
- GET /<code>    – redirects to the original URL.

Error handling:
- 400 Bad Request for missing/invalid URL.
- 404 Not Found for unknown short code.
"""

import string
import random
import threading
from typing import Dict

from flask import Flask, request, jsonify, redirect, abort
import validators

app = Flask(__name__)

# In‑memory store: code → original URL
url_map: Dict[str, str] = {}
store_lock = threading.Lock()

# Characters used for the short code (Base62)
_CODE_ALPHABET = string.ascii_letters + string.digits
_CODE_LENGTH = 6


def _generate_code() -> str:
    """Generate a random Base62 code of length `_CODE_LENGTH`.

    The function retries until a unique code is found. In practice collisions are extremely rare.
    """
    while True:
        code = ''.join(random.choices(_CODE_ALPHABET, k=_CODE_LENGTH))
        with store_lock:
            if code not in url_map:
                return code

@app.route('/shorten', methods=['POST'])
def shorten() -> tuple:
    """Create a short code for a given URL.

    Expected JSON payload: {"url": "<original_url>"}
    Returns: {"code": "<short_code>"} with HTTP 201 on success.
    Returns HTTP 400 with JSON error on validation failure.
    """
    if not request.is_json:
        abort(400, description='Request body must be JSON')
    data = request.get_json()
    url = data.get('url')
    if not url:
        abort(400, description='Missing "url" field')
    if not validators.url(url):
        abort(400, description='Invalid URL format')
    code = _generate_code()
    with store_lock:
        url_map[code] = url
    return jsonify({'code': code}), 201

@app.route('/<code>', methods=['GET'])
def redirect_to_original(code: str):
    """Redirect to the original URL for the given short code.

    If the code does not exist, returns 404.
    """
    with store_lock:
        original_url = url_map.get(code)
    if original_url is None:
        abort(404, description='Short code not found')
    return redirect(original_url, code=302)

# Custom JSON error responses
@app.errorhandler(400)
def handle_400(error):
    response = jsonify({'error': error.description if hasattr(error, 'description') else str(error)})
    response.status_code = 400
    return response

@app.errorhandler(404)
def handle_404(error):
    response = jsonify({'error': error.description if hasattr(error, 'description') else str(error)})
    response.status_code = 404
    return response

if __name__ == '__main__':
    # Run the Flask development server; in production a WSGI server would be used.
    app.run(host='0.0.0.0', port=5000, debug=False)
```

### Validation
```bash
# Install dependencies (if not already done)
pip install -r requirements.txt

# Run the app in the background (or in another terminal)
python app.py &
# Give it a moment to start, then test the endpoints:
# 1. Valid POST
curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "https://example.com"}' | jq .
# Expected output: {"code": "<6‑char>"}

# 2. GET redirect (replace <code> with the value from step 1)
curl -i http://127.0.0.1:5000/<code>
# Expected: HTTP/1.1 302 FOUND with Location: https://example.com

# 3. Bad URL POST
curl -s -X POST http://127.0.0.1:5000/shorten \
     -H "Content-Type: application/json" \
     -d '{"url": "not-a-url"}' | jq .
# Expected: {"error": "Invalid URL format"}

# 4. Unknown code GET
curl -i http://127.0.0.1:5000/unknown123
# Expected: HTTP/1.1 404 NOT FOUND with JSON error

# Stop the server (if run in background)
kill %1
```
