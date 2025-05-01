# Fixing the gunicorn Startup Issue

We've implemented several solutions to fix the `gunicorn: not found` error in your Docker container:

## Summary of Changes

1. **Added gunicorn to requirements.txt**

   - Explicitly added `gunicorn==21.2.0` to ensure it's installed

2. **Created Multiple Startup Scripts with Fallbacks**

   - `enhanced_startup.sh`: Now checks for gunicorn and falls back to uvicorn
   - `start_server.sh`: Simple script focused on starting the server properly
   - `universal_start.sh`: Comprehensive script handling database and server startup
   - `emergency_start.sh`: Last resort script that installs packages on demand

3. **Updated Docker Configuration**

   - Modified Dockerfile to explicitly install gunicorn and uvicorn
   - Created new entrypoint script to verify required packages
   - Set better environment variables in docker-compose.yml

4. **Added Health Check Endpoint**

   - Created a `/api/v1/health` endpoint in the API
   - Added a health check script for Docker
   - Updated Docker health check configuration

5. **Created Helpful Management Scripts**
   - `rebuild_containers.sh`: Rebuilds containers from scratch
   - `repair_all.sh`: Comprehensive fix for all issues
   - `Makefile`: Simple commands for common operations

## How to Fix the Current Issue

To fix the current "gunicorn not found" issue, please run:

```bash
./rebuild_containers.sh
```

This will rebuild your containers with all the necessary packages installed.

If that doesn't work, you can try the repair script:

```bash
./repair_all.sh
```

## Verifying the Fix

After rebuilding, check that the API is running properly with:

```bash
docker-compose ps
```

You should see both `aed-postgres` and `aed-api` containers running.

You can view the logs to confirm there are no errors:

```bash
docker-compose logs -f api
```

Test the API is working by accessing the health endpoint:

```bash
curl http://localhost:8000/api/v1/health
```

## Troubleshooting

If issues persist:

1. Check if gunicorn is installed in the container:

   ```bash
   docker exec aed-api pip list | grep gunicorn
   ```

2. Try manually starting the API with the emergency script:

   ```bash
   docker exec aed-api ./emergency_start.sh
   ```

3. Check for any SQL connection issues:
   ```bash
   docker exec aed-api ./fix_postgres_auth.sh
   ```
