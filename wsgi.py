"""
WSGI entry point for the AED Location API application.
This provides an alternative way to run the application in production.

The presence of this file makes it easier for cloud platforms to detect
and run a Python web application.
"""

import os
from app.main import app

# This allows the application to be run with a WSGI server like Gunicorn
# Example: gunicorn wsgi:app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("wsgi:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=False)
