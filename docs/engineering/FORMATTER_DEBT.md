# Formatter debt

`backend/app/services/auth.py` is temporarily excluded from Black enforcement because its existing embedded SQL blocks use a legacy multiline-string layout that predates the current formatter contract. The module remains covered by Ruff and backend tests.

The exception is intentionally narrow. New Catalyst code and the rest of the backend continue to be checked by Black. When the auth-storage module is next refactored, remove the `extend-exclude` entry from `backend/pyproject.toml` after formatting the module in a dedicated change.
