#!/usr/bin/env python3
"""
Python script to execute BigQuery DDL schemas and configure DWH.
Usage:
    python scripts/setup_dwh.py
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.cloud import bigquery
from config.settings import get_settings


def main():
    settings = get_settings()
    project_id = settings.GCP_PROJECT_ID
    location = settings.GCP_LOCATION
    print(f"Applying BigQuery DDL for project: {project_id} (Location: {location})...")

    ddl_file = Path(__file__).resolve().parent.parent / "sql" / "ddl.sql"
    if not ddl_file.exists():
        print(f"Error: DDL file not found at {ddl_file}")
        sys.exit(1)

    ddl_sql = ddl_file.read_text(encoding="utf-8")

    try:
        client = bigquery.Client(project=project_id, location=location)
        # Execute DDL queries
        query_job = client.query(ddl_sql)
        query_job.result()  # Wait for completion
        print("Successfully applied BigQuery DDL schemas, tables, and views.")
    except Exception as e:
        print(f"Warning/Error executing DDL: {e}")
        print("If GCP credentials are not yet configured, DDL will be applied upon first deployment.")


if __name__ == "__main__":
    main()
