# AED Location API

A RESTful API service for retrieving and reporting Automated External Defibrillator (AED) locations in Hong Kong.

## Features

- Retrieve AED locations with comprehensive information
- Find nearby AEDs based on user coordinates
- Report issues with specific AEDs
- Utility endpoints for system health and statistics

## API Endpoints

### AED Endpoints

- `GET /api/v1/aeds` - Get all AEDs with pagination and sorting options
- `GET /api/v1/aeds/nearby` - Find AEDs within specified radius of given coordinates
- `GET /api/v1/aeds/sorted-by-location` - Get all AEDs sorted by distance from given coordinates
- `POST /api/v1/aeds/{aed_id}/report` - Report an issue with an AED
- `GET /api/v1/aeds/{aed_id}/reports` - Get all reports for a specific AED
- `POST /api/v1/aeds/refresh` - Refresh AED data from official source

### Report Endpoints

- `GET /api/v1/reports` - Get all reports with pagination and filtering options
- `GET /api/v1/reports/{report_id}` - Get a specific report by ID
- `PUT /api/v1/reports/{report_id}/status` - Update the status of a report

### Utility Endpoints

- `GET /api/v1/utils/health` - Health check endpoint for the API and database
- `GET /api/v1/utils/info` - Get detailed system information about the service
- `GET /api/v1/utils/stats` - Get statistics about AEDs and reports in the system
- `GET /api/v1/utils/validate-geo` - Validate geospatial data integrity
- `GET /api/v1/utils/coverage` - Evaluate AED coverage for a specific area
- `GET /api/v1/utils/logs` - Get recent log entries from the application

## Setup and Installation

### Prerequisites

- Docker and Docker Compose
- PostgreSQL with PostGIS extension
- Python 3.9+

### Environment Variables

Create a `.env` file with the following variables:

```
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=aed_db
DB_HOST=db
POSTGRES_SUPERUSER=postgres
POSTGRES_SUPERUSER_PASSWORD=postgres
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=admin
```

### Running with Docker Compose

1. Build and start the containers:

```bash
docker-compose up -d
```

2. Access the API at `http://localhost:8000`

3. Access PgAdmin at `http://localhost:8181`

## Development

### Installation for Local Development

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

```bash
uvicorn app.main:app --reload
```

### Testing

Run the tests with:

```bash
pytest
```

## Documentation

API documentation is available at:

- Swagger UI: `/api/v1/docs`
- ReDoc: `/api/v1/redoc`
- OpenAPI JSON: `/api/v1/openapi.json`

## Deployment

### Deploying to Zeabur

This project can be easily deployed to [Zeabur](https://zeabur.com/), a modern cloud platform.

1. Create an account on Zeabur and install the CLI and required tools:

```bash
npm install -g zeabur-cli
brew install jq  # Required for JSON parsing in the deployment script
```

2. Log in to Zeabur:

```bash
zeabur login
```

3. Set the environment variables in a `.env` file (do not commit this file):

```env
DATABASE_URL=postgresql://user:password@host/dbname
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_NAME=aed_db
DB_HOST=your-db-host
POSTGRES_SUPERUSER=postgres
POSTGRES_SUPERUSER_PASSWORD=superuserpassword
```

4. Run the deployment script:

**Option 1: Advanced deployment with environment variable management**

```bash
source .env  # Load environment variables
./deploy-zeabur.sh
```

The script will:

- Create a new project named "aed-location-api" if it doesn't exist
- Deploy your service to Zeabur
- Set up all required environment variables
- Expose the service to a public URL

**Option 2: Simple deployment (recommended for beginners)**

```bash
./deploy-simple.sh
```

This simpler script:

- Has fewer dependencies (no jq required)
- Deploys the current directory to Zeabur
- Prompts for database connection if needed
- Provides clear instructions for next steps

### Setting up PostgreSQL on Zeabur

For the AED API to work correctly, you'll need a PostgreSQL database with PostGIS extension.
See the [PostgreSQL Setup Guide](docs/zeabur-postgres-setup.md) for detailed instructions on setting up a PostgreSQL database on Zeabur.

Alternatively, you can deploy directly from the Zeabur dashboard by connecting your GitHub repository.

## License

[MIT License](LICENSE)
