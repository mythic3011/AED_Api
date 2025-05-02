#!/bin/bash
# Script to run after PostgreSQL initialization

# Copy our custom pg_hba.conf file to the correct location
if [ -f "/docker-entrypoint-initdb.d/pg_hba.conf" ]; then
  echo "Copying custom pg_hba.conf file..."
  cp /docker-entrypoint-initdb.d/pg_hba.conf /var/lib/postgresql/data/
  echo "pg_hba.conf has been updated successfully."
else
  echo "Warning: Custom pg_hba.conf file not found."
fi

# Grant necessary permissions to the file
chmod 600 /var/lib/postgresql/data/pg_hba.conf
chown postgres:postgres /var/lib/postgresql/data/pg_hba.conf

echo "PostgreSQL custom configuration completed."
