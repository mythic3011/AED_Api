#!/bin/bash
# Script to fix permissions for PostgreSQL init scripts
# This script should be run before starting PostgreSQL

# Fix line endings on all shell scripts
find /docker-entrypoint-initdb.d -type f -name "*.sh" -exec dos2unix {} \;

# Make all scripts in the initdb directory executable
chmod +x /docker-entrypoint-initdb.d/*.sh

# Print confirmation
echo "Fixed permissions for all PostgreSQL init scripts"

# Execute the original script that was part of the entrypoint
exec "$@"
