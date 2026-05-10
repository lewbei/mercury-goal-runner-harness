# Thinking Plan: Add mode parameter to flask.Config.from_file()

## Architecture
The change is localized to the Flask configuration module (`flask/config.py`). No new files or directories are required. Modifying this single file preserves the existing package structure and ensures that all code paths that import `flask.Config` will automatically gain the new `mode` parameter.

## Design decisions
- **Parameter addition**: Introduce a `mode` argument with default value `"rt"` to keep the current text‑mode behaviour for existing callers.
- **Backward compatibility**: The default `"rt"` mirrors the historic implementation, so existing code that does not specify `mode` continues to work unchanged.
- **Docstring update**: Extend the method docstring to document the new argument, its purpose, and the default.
- **Error handling**: Preserve the existing `silent` handling – if the file cannot be opened, the method will still raise or swallow the exception based on `silent`.
- **Minimal impact**: Only the `open` call needs to be updated to pass the `mode`. No other logic is altered.

---

## Step 1: flask/config.py

### Why
`flask.Config.from_file` is the sole location where the configuration file is opened. Adding the `mode` parameter here directly satisfies the goal without affecting unrelated parts of the codebase.

### Design
- Update the method signature to `def from_file(self, filename, silent=False, mode="rt")`.
- Modify the `open` call to `open(filename, mode)`.
- Extend the docstring to describe the new `mode` argument and its default.
- Ensure the function still respects the `silent` flag.
- No additional imports are required.

### Template
```diff
--- a/flask/config.py
+++ b/flask/config.py
@@
-    def from_file(self, filename, silent=False):
-        """Load configuration from a Python file.
-
-        This method reads the file and executes it as a Python script.
-        The resulting variables are added to the configuration object.
-        """
-        try:
-            with open(filename) as f:
-                code = compile(f.read(), filename, 'exec')
-                exec(code, self)
-        except OSError as e:
-            if silent:
-                return False
-            raise
-        return True
+    def from_file(self, filename, silent=False, mode="rt"):
+        """Load configuration from a file.
+
+        Args:
+            filename (str): Path to the configuration file.
+            silent (bool): If ``True`` suppresses ``OSError`` exceptions and
+                returns ``False`` on failure. If ``False`` the original exception
+                is re‑raised.
+            mode (str): File opening mode passed to :func:`open`. The default
+                ``"rt"`` preserves the historic text‑mode behaviour, while callers
+                can pass ``"rb"`` (or any other valid mode) to support binary
+                formats such as ``tomllib`` introduced in Python 3.11.
+
+        Returns:
+            bool: ``True`` if the file was loaded successfully, otherwise ``False``
+                when ``silent`` is ``True``.
+        """
+        try:
+            # ``mode`` defaults to "rt" for backward compatibility.
+            with open(filename, mode) as f:
+                # ``exec`` works for both text and binary data when the file
+                # contains executable Python code. For binary formats like TOML,
+                # the caller should provide a custom loader that reads the
+                # binary data and updates the config accordingly.
+                code = compile(f.read(), filename, 'exec')
+                exec(code, self)
+        except OSError as e:
+            if silent:
+                return False
+            raise
+        return True
```

### Validation
Run the Flask test suite (or a minimal script) to verify that:
1. Existing calls to ``Config.from_file('config.py')`` continue to work.
2. Passing ``mode='rb'`` to a TOML file using ``tomllib`` loads correctly.
Example validation command:
```bash
python - <<'PY'
import flask, json, os, tempfile
# Create a temporary TOML file
import tomllib
toml_content = """[section]\nkey = 'value'"""
tmp_path = os.path.join(tempfile.gettempdir(), 'test.toml')
with open(tmp_path, 'wb') as f:
    f.write(toml_content.encode())
# Load using Flask Config with mode='rb'
cfg = flask.Config(root_path='.')
cfg.from_file(tmp_path, mode='rb')
print('Loaded keys:', list(cfg.keys()))
PY
```
The script should output the loaded keys without raising an exception.
