#!/bin/bash
set -e

echo "🚀 AED API Container Entrypoint 🚀"
echo "Current directory: $(pwd)"
echo "Listing /app directory:"
ls -la /app
echo "Listing /scripts directory:"
ls -la /scripts || echo "/scripts directory not found"

# Define fallback function for direct uvicorn execution
start_with_uvicorn() {
    echo "Starting with direct uvicorn execution"
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
}

# Create a startup script if no scripts are available
if [ ! -f /app/universal_start.sh ] && [ ! -f /scripts/universal_start.sh ]; then
    echo "Creating a simple startup script"
    cat > /tmp/simple_start.sh << 'EOF'
#!/bin/bash
set -e
echo "🚀 Simple Startup Script 🚀"
export PORT=${PORT:-8000}
echo "Starting server on port $PORT"
uvicorn app.main:app --host 0.0.0.0 --port $PORT
EOF
    chmod +x /tmp/simple_start.sh
    exec /tmp/simple_start.sh
fi

# Try to run the universal_start.sh script from different locations
for script_path in "/app/universal_start.sh" "/scripts/universal_start.sh" "/scripts/failsafe_start.sh"; do
    if [ -f "$script_path" ]; then
        echo "Found startup script at $script_path"
        # Convert to unix line endings just in case
        dos2unix "$script_path" 2>/dev/null || true
        chmod +x "$script_path" 2>/dev/null || true
        echo "Content of $script_path (first 10 lines):"
        cat "$script_path" | head -10
        echo "Executing $script_path..."
        # Execute directly without shell interpretation
        exec "$script_path"
        # If exec failed, this code should not be reached
        echo "Execution failed, trying another approach"
        bash "$script_path"
        exit 0
    fi
done

# If we got here, no scripts worked - fall back to uvicorn directly
start_with_uvicorn
