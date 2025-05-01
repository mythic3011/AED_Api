# Makefile for AED API management

.PHONY: build start stop restart logs clean test test-reports test-sql-injection install-deps help

# Default target when running make with no arguments
help:
	@echo "AED API Management Commands"
	@echo "--------------------------"
	@echo "make build          - Build the Docker containers"
	@echo "make start          - Start the Docker containers"
	@echo "make stop           - Stop the Docker containers"
	@echo "make restart        - Restart the Docker containers"
	@echo "make logs           - View container logs"
	@echo "make clean          - Remove containers and volumes"
	@echo "make test           - Run all tests"
	@echo "make test-reports   - Test report endpoints"
	@echo "make test-sql-injection - Test SQL injection protection"
	@echo "make fix-auth       - Fix PostgreSQL authentication issues"
	@echo "make install-deps   - Install Python dependencies locally"
	@echo "make help           - Show this help message"

# Build the Docker containers
build:
	docker-compose build

# Start the Docker containers
start:
	docker-compose up -d

# Stop the Docker containers
stop:
	docker-compose down

# Restart the Docker containers
restart: stop start

# View the container logs
logs:
	docker-compose logs -f

# Remove containers and volumes (caution - will delete data!)
clean:
	docker-compose down -v

# Run all tests
test: test-reports test-sql-injection

# Test report endpoints
test-reports:
	./test_report_api.sh

# Test SQL injection protection
test-sql-injection:
	./test_sql_injection.sh

# Fix PostgreSQL authentication issues
fix-auth:
	./fix_postgres_auth.sh

# Install Python dependencies locally (useful for development)
install-deps:
	pip install -r requirements.txt
