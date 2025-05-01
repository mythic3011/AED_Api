#!/bin/bash
# Docker entrypoint script to ensure gunicorn is available

echo "🔍 Checking for required packages..."

# Install required packages if not available
if ! command -v gunicorn &> /dev/null; then
    echo "📦 Installing gunicorn..."
    pip install --no-cache-dir gunicorn
fi

if ! command -v uvicorn &> /dev/null; then
    echo "📦 Installing uvicorn..."
    pip install --no-cache-dir uvicorn
fi

# Run the enhanced startup script
echo "🚀 Running enhanced startup script..."
exec ./enhanced_startup.sh
