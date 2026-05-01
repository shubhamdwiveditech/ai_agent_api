import os
import sys
import requests
from app.core.config import settings

# Configuration
OUTPUT_DIR = "./supabase/functions"

# python -m app.utils.download_supabase_functions

def download_functions():
    """Download all public functions from Supabase via REST API"""

    if not settings.supabase_url or not settings.supabase_key:
        print("Error: SUPABASE_URL and SUPABASE_KEY environment variables required")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    headers = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json"
    }

    query = """
        SELECT 
            r.routine_name,
            r.routine_type,
            r.data_type AS return_type,
            d.function_definition AS routine_definition
        FROM information_schema.routines r
        LEFT JOIN LATERAL fn_get_def(r.routine_name) d ON true
        WHERE r.routine_schema = 'public'
        ORDER BY r.routine_name
    """

    try:
        # Call execute_query RPC via REST
        response = requests.post(
            f"{settings.supabase_rest_url}/execute_query",
            headers=headers,
            json={"query": query}
        )

        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            sys.exit(1)

        functions = response.json()

        # execute_query returns json_agg, may be wrapped
        if isinstance(functions, str):
            import json
            functions = json.loads(functions)

        if not functions:
            print("No functions found")
            return

        count = 0
        for func in functions:
            func_name = func.get("routine_name", "unknown")
            func_def  = func.get("routine_definition") or "-- definition not available"

            filename = f"{OUTPUT_DIR}/{func_name}.sql"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(func_def)

            print(f"✓ Saved: {filename}")
            count += 1

        print(f"\nSuccessfully downloaded {count} functions to {OUTPUT_DIR}/")

    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    download_functions()