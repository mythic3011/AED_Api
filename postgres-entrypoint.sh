#!/bin/bash
set -e

# Convert script to Unix format and make executable
dos2unix "$0" >/dev/null 2>&1 || true
chmod +x "$0"

# Process the postgres entry point script files
echo "Processing PostgreSQL init scripts..."
for f in /docker-entrypoint-initdb.d/*.sh; do
  dos2unix "$f" >/dev/null 2>&1
  chmod +x "$f"
  echo "Fixed permissions for $f"
done

# Execute original entrypoint
echo "Starting PostgreSQL with custom entrypoint..."
exec docker-entrypoint.sh postgres "$@"
