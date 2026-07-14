import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app  # noqa: E402

# Vercel's Python runtime looks for a module-level variable named `app`
# (or `handler`) that is a WSGI application.
