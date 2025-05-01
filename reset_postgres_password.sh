#!/bin/bash
# Script to reset PostgreSQL password inside the container

# Check if superuser password env var is available
if [ -z "$POSTGRES_PASSWORD" ]; then
  echo "Error: POSTGRES_PASSWORD environment variable not set"
  exit 1
fi

# Create SQL to reset password
cat > /tmp/reset_password.sql << EOF
ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';
EOF

# Execute the SQL
if [ -f /tmp/reset_password.sql ]; then
  echo "Resetting PostgreSQL password..."
  psql -U postgres -d postgres -f /tmp/reset_password.sql
  echo "Password reset complete."
  rm /tmp/reset_password.sql
else
  echo "Error creating SQL script"
  exit 1
fi
