#!/usr/bin/env bash
# =====================================================================
# GCP Infrastructure Setup Script
# YouTube Analytics Platform (Sprint 1)
# =====================================================================

set -eo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "agentverse-guardian-gcloud")
REGION="us-central1"
BIGQUERY_LOCATION="US"
QUEUE_NAME="telegram-tasks"

echo "=== Setting up GCP Infrastructure for Project: ${PROJECT_ID} (Region: ${REGION}) ==="

# 1. Enable Required GCP APIs
echo "1. Enabling required Google Cloud APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudtasks.googleapis.com \
    firestore.googleapis.com \
    bigquery.googleapis.com \
    aiplatform.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com \
    youtube.googleapis.com \
    --project="${PROJECT_ID}"

# 2. Create Cloud Tasks Queue for Telegram Webhooks
echo "2. Configuring Cloud Tasks Queue: ${QUEUE_NAME}..."
if gcloud tasks queues describe "${QUEUE_NAME}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Cloud Tasks Queue ${QUEUE_NAME} already exists."
else
    gcloud tasks queues create "${QUEUE_NAME}" \
        --location="${REGION}" \
        --max-attempts=5 \
        --max-retry-duration=300s \
        --max-concurrent-dispatches=20 \
        --max-dispatches-per-second=10 \
        --project="${PROJECT_ID}"
    echo "Cloud Tasks Queue ${QUEUE_NAME} created successfully."
fi

# 3. Create BigQuery Dataset and Tables from DDL
echo "3. Applying BigQuery DDL schema..."
bq query --use_legacy_sql=false \
    --project_id="${PROJECT_ID}" \
    --location="${BIGQUERY_LOCATION}" \
    < sql/ddl.sql

# 4. Configure Firestore Database (Native Mode) and TTL Policy
echo "4. Checking Firestore (Native Mode) and TTL settings..."
# Ensure database exists
if ! gcloud firestore databases describe --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo "Creating default Firestore database in Native Mode..."
    gcloud firestore databases create --location="${REGION}" --type=firestore-native --project="${PROJECT_ID}" || true
fi

# Set TTL Policy for api_cache collection on expires_at field
echo "Enabling TTL policy on api_cache(expires_at)..."
gcloud firestore fields ttls update expires_at \
    --collection-group=api_cache \
    --enable-ttl \
    --project="${PROJECT_ID}" 2>/dev/null || echo "TTL policy on expires_at already configured or scheduled."

echo "=== GCP Infrastructure Setup Completed Successfully! ==="
