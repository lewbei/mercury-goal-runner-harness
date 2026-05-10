# Thinking Plan: URL shortener service

## Architecture
The service consists of two artifacts:
- **app.py** – the main Flask application implementing the API, in‑memory storage, and utility functions.
- **requirements.txt** – declares the third‑party dependencies (Flask). No additional modules are required because URL validation is performed with the standard library (`urllib.parse`).

The architecture is deliberately minimal to satisfy the goal contract while keeping the code easy to understand and test. All logic lives in a single module (`app.py`) because the service is small, stateless, and runs in a single process. In‑memory storage (`dict`) is used as specified; persistence is not needed.

## Design decisions
### Code generation
| Option | Description | Pros | Cons | Chosen? |
|--------|-------------|------|------|---------|
| **Random alphanumeric** (6‑character) | Generate a random string using `random.choices` and retry on collision. | Simple, no state, low probability of collision, no need for a counter. | Theoretical chance of collision (negligible). | ✅ |
| Sequential integer (base62) | Increment a counter and encode to base62. | Predictable length, no collisions. | Requires mutable global counter, possible race conditions, more code. | ❌ |
| Hash of URL (e.g., SHA‑256 truncated) | Derive code from the original URL. | Deterministic, same URL yields same code. | Collisions possible, longer computation, may expose original URL pattern. | ❌ |

We selected the **random alphanumeric** approach because it is stateless, easy to implement, and meets the requirement for a short code without additional complexity.

### URL validation
| Option | Description | Pros | Cons | Chosen? |
|--------|-------------|------|------|---------|
| `validators` third‑party library | Use `validators.url`. | Robust validation, handles many edge cases. | Adds an extra dependency for a simple check. | ❌ |
| `urllib.parse` from stdlib | Parse URL and ensure scheme is http/https and netloc is present. | No extra dependency, sufficient for typical use cases. | Slightly less thorough than a dedicated validator. | ✅ |

We use `urllib.parse` to keep the dependency footprint minimal (only Flask).

### Error handling
- **Invalid request body** → `400 Bad Request` with a clear message.
- **Invalid URL** → `400 Bad Request`.
- **Missing short code** → `404 Not Found`.
- All error responses use Flask's `abort` with a description, which Flask turns into a JSON error payload when the request is JSON (default HTML is acceptable for this simple service).

### In‑memory storage
A plain Python `dict` (`url_map`) maps short codes to original URLs. This satisfies the “in‑memory” requirement and works for the single‑process development server. No thread‑safety mechanisms are added because Flask's built‑in server processes requests sequentially by default; if deployed with a multi‑threaded server, the GIL still protects the dict for simple operations.

---

## Step 1: app.py

### Why
`app.py` is the core of the service. It defines the Flask application, the in‑memory store, utility functions for URL validation and code generation, and the two required endpoints (`POST /shorten` and `GET /<code>`). All subsequent steps depend on this file being present and functional.

### Design
- **Imports**: standard library (`string`, `random`, `logging`, `urllib.parse`) and Flask components.
- **Configuration**: `CODE_LENGTH` and `CODE_CHARSET` are configurable constants.
- **Utility functions**:
  - `_is_valid_url(url)` validates URLs using `urllib.parse`.
  - `_generate_code()` creates a unique random code, retrying on collision.
- **Endpoints**:
  - `POST /shorten` expects JSON `{ "url": "..." }`. It validates the payload, checks the URL, generates a code, stores the mapping, and returns `{ "code": "..." }` with HTTP 201.
  - `GET /<code>` looks up the code; if found, redirects (`302`) to the original URL; otherwise aborts with 404.
  - Optional `/health` endpoint for quick health checks.
- **Error handling**: uses `abort` with appropriate status codes and descriptive messages.
- **Logging**: basic INFO logs for creation and redirection events.
- **Running**: `if __name__ == "__main__"` block runs the Flask development server on `0.0.0.0:5000`.

Edge cases handled:
- Missing or non‑JSON body → 400.
- Empty or non‑string `url` field → 400.
- Invalid URL format → 400.
- Code collision (extremely unlikely) → retry until unique.
- Unknown short code → 404.

### Template
```python
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
defndef shorten() -> tuple[dict, int]:
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
```

### Validation
1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the service**:
   ```bash
   python app.py
   ```
   The server should start listening on `http://0.0.0.0:5000`.
3. **Test POST /shorten** (valid URL):
   ```bash
   curl -s -X POST -H "Content-Type: application/json" -d '{"url":"https://example.com"}' http://127.0.0.1:5000/shorten
   ```
   Expected output: JSON containing a `code` field and HTTP status 201.
4. **Test POST /shorten** (invalid URL):
   ```bash
   curl -s -X POST -H "Content-Type: application/json" -d '{"url":"not-a-url"}' http://127.0.0.1:5000/shorten -w "%{http_code}\n"
   ```
   Expected HTTP status 400.
5. **Test GET /<code>** (existing code):
   Assuming the previous POST returned `"code":"abc123"`:
   ```bash
   curl -i http://127.0.0.1:5000/abc123
   ```
   Expected HTTP status 302 with a `Location: https://example.com` header.
6. **Test GET /<code>** (missing code):
   ```bash
   curl -i http://127.0.0.1:5000/nonexistent -w "%{http_code}\n"
   ```
   Expected HTTP status 404.
7. **Health check** (optional):
   ```bash
   curl http://127.0.0.1:5000/health
   ```
   Expected JSON `{ "status": "ok" }` with status 200.

If all commands succeed, the step satisfies the done criteria:
- `app.py` runs.
- `POST` returns JSON.
- `GET` redirects.
- `400` on bad URL.
- `404` on missing code.

---

## Step 2: requirements.txt

### Why
`requirements.txt` lists the external packages needed to run the service. It is required for reproducible installation and satisfies the contract's `final_outputs` list.

### Design
Only Flask is required. Pinning to a minimum version (`>=2.2`) ensures compatibility with the code (type hints, `dict[str, str]` syntax) while allowing newer bug fixes.

### Template
```text
Flask>=2.2
```

### Validation
```bash
# Create a fresh virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate
pip install -r requirements.txt
# Verify Flask is installed
python -c "import flask; print('Flask version:', flask.__version__)"
```
If the import succeeds and prints a version >= 2.2, the step is successful.

---

## Verification of Done Criteria
| Criterion | How it is verified |
|-----------|--------------------|
| `app.py` runs | `python app.py` starts the Flask server without errors. |
| `POST` returns JSON | `curl` request to `/shorten` returns a JSON payload with a `code` field and HTTP 201. |
| `GET` redirects | `curl -i /<code>` returns HTTP 302 and a `Location` header pointing to the original URL. |
| `400` on bad URL | `curl` request with an invalid URL receives HTTP 400. |
| `404` on missing | `curl -i /nonexistent` receives HTTP 404. |

All criteria are addressed by the steps above.
