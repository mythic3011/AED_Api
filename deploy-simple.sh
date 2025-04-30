#!/bin/bash
# Simple Zeabur Deployment Script
# This script provides a more straightforward approach to deploying to Zeabur
# without complex dependencies like jq

# Exit on any error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}== AED API Zeabur Deployment Script ==${NC}"
echo -e "${YELLOW}Checking Zeabur CLI...${NC}"

# Check if zeabur-cli is installed
if ! command -v zeabur &> /dev/null; then
    echo -e "${RED}Error: zeabur-cli not found. Please install with:${NC}"
    echo "npm install -g zeabur-cli"
    exit 1
fi

echo -e "${YELLOW}Logging in to Zeabur...${NC}"

# Check if already logged in
LOGGED_IN=false
if zeabur whoami &>/dev/null; then
    USER=$(zeabur whoami)
    echo -e "${GREEN}Logged in as: $USER${NC}"
    LOGGED_IN=true
else
    echo -e "${YELLOW}Please login to Zeabur:${NC}"
    zeabur login
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Login failed. Please try again.${NC}"
        exit 1
    fi
fi

# Get DATABASE_URL if not set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}DATABASE_URL not set. Enter PostgreSQL connection string:${NC}"
    read -s DATABASE_URL
    export DATABASE_URL
fi

echo -e "${GREEN}Deploying to Zeabur...${NC}"
echo "This may take a few minutes..."

# Simply deploy the current folder
zeabur deploy

echo -e "${GREEN}Deployment complete!${NC}"
echo -e "${YELLOW}Visit your Zeabur dashboard to check the deployment status and configure variables.${NC}"
echo -e "${YELLOW}Don't forget to set up the PostgreSQL database and PostGIS extension.${NC}"
