# Zeabur Deployment Files

This directory contains files related to deploying the AED Location API on Zeabur.

## Files

- `zeabur.json` - Main configuration file for Zeabur
- `service.json` - Additional service configuration
- `.zeabur/builder.json` - Build process configuration
- `Procfile` - Process type declaration
- `runtime.txt` - Python version specification
- `deploy-zeabur.sh` - Advanced deployment script (requires jq)
- `deploy-simple.sh` - Simple deployment script
- `wsgi.py` - WSGI entry point for alternative deployment methods

## Deployment Process

1. Install the Zeabur CLI: `npm install -g zeabur-cli`
2. Log in to Zeabur: `zeabur login`
3. Deploy using either:
   - Simple method: `./deploy-simple.sh`
   - Advanced method: `./deploy-zeabur.sh` (requires jq)

## Environment Variables

The following environment variables should be configured in Zeabur:

- `DATABASE_URL` - PostgreSQL connection string
- `DB_USER` - PostgreSQL username
- `DB_PASSWORD` - PostgreSQL password
- `DB_NAME` - PostgreSQL database name
- `DB_HOST` - PostgreSQL host
- `POSTGRES_SUPERUSER` - PostgreSQL superuser for PostGIS setup
- `POSTGRES_SUPERUSER_PASSWORD` - PostgreSQL superuser password

## Verification

After deployment, access the following URL to verify that the deployment was successful:

```
https://your-zeabur-app-url.zeabur.app/api/v1/utils/zeabur-verify
```

This endpoint will provide information about the Zeabur deployment environment.
