# Setting up PostgreSQL on Zeabur

This guide explains how to set up a PostgreSQL database on Zeabur for use with the AED Location API.

## Steps

### 1. Create a PostgreSQL Service on Zeabur

1. Log in to your Zeabur dashboard
2. Select your project (create a new one if needed)
3. Click "Add Service"
4. Select "Marketplace"
5. Choose "PostgreSQL"
6. Wait for the database to be provisioned

### 2. Get PostgreSQL Connection Information

1. Once the PostgreSQL service is created, click on it
2. Go to the "Environment Variables" tab
3. Look for the following environment variables:
   - `POSTGRES_HOST` - The hostname of the database
   - `POSTGRES_PORT` - The port (usually 5432)
   - `POSTGRES_USER` - The database username
   - `POSTGRES_PASSWORD` - The database password
   - `POSTGRES_DATABASE` - The default database name

### 3. Install PostGIS Extension

Zeabur PostgreSQL does not come with PostGIS pre-installed. You'll need to connect to the database and install it:

1. Install the PostgreSQL client on your local machine:

   ```bash
   brew install postgresql
   ```

2. Connect to the database:

   ```bash
   PGPASSWORD=your_password psql -h hostname -U username -d database_name
   ```

3. Install the PostGIS extension:

   ```sql
   CREATE EXTENSION postgis;
   ```

4. Verify the installation:
   ```sql
   SELECT PostGIS_version();
   ```

### 4. Set Up Environment Variables for Your API Service

1. Go to your AED API service in Zeabur
2. Go to the "Environment Variables" tab
3. Add the following environment variables:
   - `DATABASE_URL`: `postgresql://username:password@hostname:port/database_name`
   - `DB_USER`: The PostgreSQL username
   - `DB_PASSWORD`: The PostgreSQL password
   - `DB_NAME`: The database name
   - `DB_HOST`: The PostgreSQL hostname
   - `POSTGRES_SUPERUSER`: Same as DB_USER for Zeabur
   - `POSTGRES_SUPERUSER_PASSWORD`: Same as DB_PASSWORD for Zeabur

### 5. Connect Your API to the Database

After setting up the environment variables, redeploy your service to ensure it connects to the PostgreSQL database:

1. Go to your AED API service
2. Click "Redeploy"
3. Once deployed, verify connectivity by accessing the health endpoint:
   ```
   https://your-deployment-url.zeabur.app/api/v1/utils/health
   ```

The health check should show that the database connection is healthy.

### 6. Initialize the Database

To initialize the database with the AED data:

1. Access the refresh endpoint to import data:

   ```
   POST https://your-deployment-url.zeabur.app/api/v1/aeds/refresh
   ```

2. Use the stats endpoint to verify data was imported:
   ```
   GET https://your-deployment-url.zeabur.app/api/v1/utils/stats
   ```

## Troubleshooting

- **Connection Issues**: Verify that the environment variables are correct
- **PostGIS Not Found**: Ensure the PostGIS extension was successfully installed
- **Data Import Failures**: Check the application logs in Zeabur for details
