#!/bin/bash
# Simple server start script with fallbacks

echo "Starting AED API server..."

# Install required packages if missing
if ! pip list | grep -q gunicorn; then
  echo "Installing gunicorn..."
  pip install --no-cache-dir gunicorn
fi

if ! pip list | grep -q uvicorn; then
  echo "Installing uvicorn..."
  pip install --no-cache-dir uvicorn
fi

# Get PORT from environment or use default
PORT=${PORT:-8000}
echo "Using port: $PORT"

# Try to start with gunicorn
echo "Attempting to start with gunicorn..."
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT --timeout 120 || {
  # If gunicorn fails, fall back to uvicorn
  echo "Gunicorn failed, falling back to uvicorn..."
  uvicorn app.main:app --host 0.0.0.0 --port $PORT || {
    # Last resort - python module
    echo "Uvicorn failed, falling back to python..."
    python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT
  }
}
