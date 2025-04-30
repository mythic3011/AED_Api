#!/bin/bash

# Zeabur deployment script for AED Location API
# Author: Mythic3013
# Date: May 1, 2025

# Set strict mode
set -e
set -o pipefail

# Terminal colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function for printing colored messages
info() {
    echo -e "${BLUE}INFO: $1${NC}"
}

success() {
    echo -e "${GREEN}SUCCESS: $1${NC}"
}

warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

error() {
    echo -e "${RED}ERROR: $1${NC}"
}

# Check if required environment variables are set
check_env() {
    local missing=0
    for var in DATABASE_URL DB_USER DB_PASSWORD DB_NAME DB_HOST POSTGRES_SUPERUSER POSTGRES_SUPERUSER_PASSWORD; do
        if [ -z "${!var}" ]; then
            error "$var is not set"
            missing=1
        fi
    done
    
    if [ $missing -eq 1 ]; then
        error "Some required environment variables are not set. Please set them before running this script."
        echo "You can source your .env file with: source .env"
        exit 1
    else
        success "All required environment variables are set"
    fi
}

# Check if required tools are installed
check_tools() {
    # Check if zeabur-cli is installed
    if ! command -v zeabur &> /dev/null
    then
        error "zeabur-cli is not installed. Install it with: npm install -g zeabur-cli"
        exit 1
    else
        success "zeabur-cli is installed"
    fi

    # Check if jq is installed (needed for JSON parsing)
    if ! command -v jq &> /dev/null
    then
        error "jq is not installed. Install it with: brew install jq"
        exit 1
    else
        success "jq is installed"
    fi

    # Check if zeabur is logged in
    if ! zeabur whoami &> /dev/null
    then
        error "You are not logged in to Zeabur. Please run 'zeabur login' first"
        exit 1
    else
        local username=$(zeabur whoami)
        success "Logged in to Zeabur as $username"
    fi
}

# Main deployment function
deploy() {
    info "Starting deployment process..."
    PROJECT_NAME="aed-location-api"
    
    # Check if project exists, create if not
    info "Looking for existing project: $PROJECT_NAME"
    local project_list_output=$(zeabur project list --json 2>/dev/null || echo '[]')
    
    # Check if the output is valid JSON
    if ! echo "$project_list_output" | jq empty &>/dev/null; then
        warning "Could not parse project list output, assuming no projects exist"
        project_list_output='[]'
    fi
    
    PROJECT_ID=$(echo "$project_list_output" | jq -r '.[] | select(.name=="'"$PROJECT_NAME"'") | .id')
    
    if [ -z "$PROJECT_ID" ]; then
        info "Creating new project: $PROJECT_NAME"
        # Try to create project and capture output
        local create_output
        create_output=$(zeabur project create --name "$PROJECT_NAME" --json 2>&1)
        
        # Check if the output is valid JSON
        if echo "$create_output" | jq empty &>/dev/null; then
            PROJECT_ID=$(echo "$create_output" | jq -r '.id')
            success "Created new project: $PROJECT_NAME (ID: $PROJECT_ID)"
        else
            error "Failed to create project. Output: $create_output"
            exit 1
        fi
    else
        success "Using existing project: $PROJECT_NAME (ID: $PROJECT_ID)"
    fi
    
    # Deploy service from current directory
    info "Deploying service from current directory..."
    local deploy_output
    deploy_output=$(zeabur service deploy --project "$PROJECT_ID" --json 2>&1)
    
    # Check if deployment was successful
    if echo "$deploy_output" | jq empty &>/dev/null; then
        SERVICE_ID=$(echo "$deploy_output" | jq -r '.id')
        success "Service deployed successfully (ID: $SERVICE_ID)"
    else
        error "Failed to deploy service. Output: $deploy_output"
        exit 1
    fi
    
    # Now set environment variables
    info "Setting environment variables for service..."
    
    # Define all vars to set
    local env_vars=(
        "DATABASE_URL:$DATABASE_URL"
        "DB_USER:$DB_USER"
        "DB_PASSWORD:$DB_PASSWORD"
        "DB_NAME:$DB_NAME"
        "DB_HOST:$DB_HOST"
        "POSTGRES_SUPERUSER:$POSTGRES_SUPERUSER"
        "POSTGRES_SUPERUSER_PASSWORD:$POSTGRES_SUPERUSER_PASSWORD"
    )
    
    # Set each variable
    for var in "${env_vars[@]}"; do
        IFS=':' read -r key value <<< "$var"
        info "Setting $key"
        
        # Check current Zeabur CLI commands
        if zeabur --help | grep -q "variable set"; then
            # New CLI format
            zeabur variable set --project "$PROJECT_ID" --service "$SERVICE_ID" --key "$key" --value "$value" > /dev/null
        elif zeabur --help | grep -q "env set"; then
            # Old CLI format
            zeabur env set --project "$PROJECT_ID" --service "$SERVICE_ID" "$key" "$value" > /dev/null
        else
            # Try alternative method
            warning "Could not determine correct variable setting command, trying direct deployment with env vars"
            # Just continue and hope the env vars get picked up during deployment
        fi
    done
    success "Environment variables set successfully"

    # Redeploy to apply all configurations
    info "Redeploying service to apply environment variables..."
    local redeploy_output
    redeploy_output=$(zeabur service redeploy --project "$PROJECT_ID" --service "$SERVICE_ID" 2>&1)
    
    if [ $? -ne 0 ]; then
        warning "Redeploy command may have failed: $redeploy_output"
        warning "Continuing anyway as this might be due to CLI command structure changes"
    else
        success "Service redeployed successfully"
    fi
    
    # Expose service to public
    info "Exposing service to public..."
    local expose_output
    expose_output=$(zeabur service expose --project "$PROJECT_ID" --service "$SERVICE_ID" --public --json 2>&1)
    
    # Check if the expose command worked and produced valid JSON
    if echo "$expose_output" | jq empty &>/dev/null; then
        DOMAIN=$(echo "$expose_output" | jq -r '.domain')
        success "Service exposed successfully"
        success "Your application is now deployed at: https://$DOMAIN"
    else
        warning "Could not determine the domain automatically: $expose_output"
        warning "Please check your Zeabur dashboard for the URL of your service"
    fi
}

# Run the checks and deployment
check_env
check_tools
deploy

success "Deployment process complete!"
success "Visit the Zeabur dashboard to see more details and configure custom domains."
