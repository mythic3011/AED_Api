import os
import sys

# Print all environment variables
print("All environment variables:")
for key, value in os.environ.items():
    print(f"{key}: {value}")

# Print database-related environment variables
print("\nDatabase environment variables:")
db_vars = ["DATABASE_URL", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME", "SUPERUSER_DATABASE_URL"]
for var in db_vars:
    print(f"{var}: {os.environ.get(var, 'NOT SET')}")

# Try to import database module and print connection values
print("\nTrying to import database module:")
try:
    sys.path.insert(0, '/app')
    from app.database import DATABASE_URL, get_superuser_engine
    print(f"DATABASE_URL from module: {DATABASE_URL}")
    try:
        superuser_url = get_superuser_engine().url
        print(f"Superuser URL: {superuser_url}")
    except Exception as e:
        print(f"Error getting superuser URL: {str(e)}")
except Exception as e:
    print(f"Error importing database module: {str(e)}")
