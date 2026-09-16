#!/usr/bin/env python3
"""
Utility script to create BigQuery dataset and tables for YouTube Analytics.
Usage:
    python scripts/setup_bigquery.py
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.services.bigquery_service import BigQueryService
from config.settings import get_settings


def main():
    settings = get_settings()
    print(f"Setting up BigQuery resources for GCP Project: {settings.GCP_PROJECT_ID}")
    print(f"Dataset: {settings.BIGQUERY_DATASET_ID} (Location: {settings.GCP_LOCATION})")

    service = BigQueryService()
    if not service.is_connected:
        print("WARNING: Could not connect to Google Cloud BigQuery.")
        print("Please check GOOGLE_APPLICATION_CREDENTIALS or gcloud auth application-default login.")
        sys.exit(1)

    success = service.init_dataset_and_tables()
    if success:
        print("Successfully created/verified BigQuery dataset and tables.")
    else:
        print("Failed to initialize BigQuery tables. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
