import pandas as pd

# API configuration for external data source
url = "https://es.hkfsd.gov.hk/aed_api/export_aed.php?lang=EN"
headers = {
    "User-Agent": "AEDEnrichmentService/1.0",
    "Accept": "text/csv",
}

# Utility function to handle CSV data and map columns
def handle_csv_data(response_text: str):
    try:
        df = pd.read_csv(
            pd.io.common.StringIO(response_text),
            encoding='utf-8',
            on_bad_lines='warn',  # Skip bad lines but warn about them
            low_memory=False  # Better handling of mixed data types
        )
        return df
    except Exception as e:
        print(f"Error parsing CSV data: {str(e)}")
        return None

# Utility function to map columns
def map_columns(df: pd.DataFrame):
    column_map = {
        "name": ["AED Name", "Name", "AEDName", "aed_name"],
        "address": ["AED Address", "Address", "AEDAddress", "aed_address"],
        "location_detail": ["Detailed location of the AED installed", "Location Detail", "DetailedLocation"],
        "lat": ["Location Google Map coordinate: latitude", "Latitude", "latitude", "lat"],
        "lng": ["Location Google Map coordinate: longitude", "Longitude", "longitude", "lng"],
        "public_use": ["Whether the AED can be used by anyone", "Public Use", "PublicUse"],
        "allowed_operators": ["Person allowed to operate the AED", "Allowed Operators", "AllowedOperators"],
        "access_persons": ["Person who has access to the AED", "Access Persons", "AccessPersons"],
        "category": ["Ground level categories", "Category", "Categories", "ground_level_categories"],
        "service_hours": ["Service Hour Remark", "Service Hours", "ServiceHours", "service_hour_remark"],
        "brand": ["AED brand", "Brand", "aed_brand"],
        "model": ["AED model", "Model", "aed_model"],
        "remark": ["AED remark", "Remark", "aed_remark", "Remarks"]
    }

    column_matches = {}
    for field, possible_columns in column_map.items():
        for col in possible_columns:
            if col in df.columns:
                column_matches[field] = col
                break

    return column_matches
