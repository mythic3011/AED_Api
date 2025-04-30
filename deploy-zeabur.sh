#!/bin/bash

# Zeabur deployment script for AED Location API
# Make sure you have installed the Zeabur CLI with:
# npm install -g zeabur-cli

# Check if zeabur-cli is installed
if ! command -v zeabur &> /dev/null
then
    echo "zeabur-cli is not installed. Install it with: npm install -g zeabur-cli"
    exit 1
fi

# Set environment variables (these will be securely stored in Zeabur)
echo "Setting up environment variables..."
zeabur env set DATABASE_URL $DATABASE_URL
zeabur env set DB_USER $DB_USER
zeabur env set DB_PASSWORD $DB_PASSWORD
zeabur env set DB_NAME $DB_NAME
zeabur env set DB_HOST $DB_HOST
zeabur env set POSTGRES_SUPERUSER $POSTGRES_SUPERUSER
zeabur env set POSTGRES_SUPERUSER_PASSWORD $POSTGRES_SUPERUSER_PASSWORD

# Deploy the application
echo "Deploying to Zeabur..."
zeabur deploy

echo "Deployment complete!"
echo "Visit your Zeabur dashboard to see the deployment status and URL."
