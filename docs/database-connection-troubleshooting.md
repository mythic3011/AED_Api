# Database Connection Troubleshooting

If you encounter database connection issues, particularly with the error "password authentication failed for user 'postgres'", follow these troubleshooting steps:

## Common Error Messages

### Password Authentication Failed

```
FATAL: password authentication failed for user "postgres"
DETAIL: Connection matched pg_hba.conf line 100: "host all all all scram-sha-256"
```

This error indicates that the application is trying to connect to PostgreSQL with incorrect credentials.

## Quick Fix Scripts

We've provided several scripts to help fix common database issues:

### 1. Use the Authentication Fix Script

```bash
./fix_postgres_auth.sh
```

This script will:

- Check if Docker is running
- Restart the PostgreSQL container with proper settings
- Reset the PostgreSQL password to match what the application expects
- Restart all services

### 2. Reset the Database (If the Quick Fix Doesn't Work)

```bash
./reset_db.sh
```

**Warning**: This will delete all data in your database!

This script:

- Stops all containers
- Removes the PostgreSQL data volume
- Starts fresh containers

### 3. Manual Fix

If the scripts don't work, you can try these steps manually:

1. Stop all containers:

   ```bash
   docker-compose down
   ```

2. Remove the PostgreSQL volume:

   ```bash
   docker volume rm enrichment_postgres_data
   ```

3. Start services again:

   ```bash
   docker-compose up -d
   ```

4. If needed, reset the PostgreSQL password:
   ```bash
   docker exec -it aed-postgres psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
   ```

## Checking Logs

Always check the logs to understand what's happening:

```bash
# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View only PostgreSQL logs
docker-compose logs db

# View only API logs
docker-compose logs api
```

## Configuration Files

These files control database connectivity:

- `.env` - Environment variables for database connections
- `docker-compose.yml` - Container configuration
- `app/database.py` - SQLAlchemy database connection
- `start_with_db_check.sh` - Startup script with database connectivity checks
- `enhanced_startup.sh` - Improved startup script with authentication retry logic

## Testing Connectivity

You can test database connectivity directly:

```bash
# Connect to PostgreSQL
docker exec -it aed-postgres psql -U postgres

# Test from API container
docker exec -it aed-api bash -c 'PGPASSWORD=postgres psql -h db -U postgres -c "SELECT 1"'
```
