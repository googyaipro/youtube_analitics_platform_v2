#!/usr/bin/env bash
# =====================================================================
# Deployment script for all 3 Cloud Run microservices:
# 1. code-sandbox (Internal, 512MB RAM, read-only)
# 2. youtube-analyst-backend (FastAPI + ADK Agent)
# 3. youtube-dashboard (Streamlit UI)
# =====================================================================

set -eo pipefail

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "gen-lang-client-0428255657")
REGION="us-central1"
REGISTRY="us-central1-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy"

echo "=== Deploying YouTube Analytics Platform Services to GCP (${PROJECT_ID}) ==="

# -------------------------------------------------------------
# 1. Deploy Service 3: Code Sandbox (512MB RAM)
# -------------------------------------------------------------
echo "1. Checking/Deploying 'code-sandbox'..."
if ! gcloud run services describe code-sandbox --region "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud run deploy code-sandbox \
        --source ./services/sandbox \
        --platform managed \
        --region "${REGION}" \
        --ingress all \
        --memory 512Mi \
        --cpu 1 \
        --min-instances 0 \
        --max-instances 5 \
        --project "${PROJECT_ID}" \
        --allow-unauthenticated
else
    echo "Service 'code-sandbox' is already active."
fi

SANDBOX_URL=$(gcloud run services describe code-sandbox --region "${REGION}" --format="value(status.url)" --project "${PROJECT_ID}")
echo "Sandbox URL: ${SANDBOX_URL}"

# -------------------------------------------------------------
# 2. Deploy Service 1: YouTube Analyst Backend
# -------------------------------------------------------------
echo "2. Building and deploying 'youtube-analyst-backend'..."
gcloud run deploy youtube-analyst-backend \
    --source . \
    --platform managed \
    --region "${REGION}" \
    --ingress all \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars "SANDBOX_SERVICE_URL=${SANDBOX_URL},GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},GEMINI_MODEL=gemini-3.5-flash" \
    --project "${PROJECT_ID}" \
    --allow-unauthenticated

BACKEND_URL=$(gcloud run services describe youtube-analyst-backend --region "${REGION}" --format="value(status.url)" --project "${PROJECT_ID}")
echo "Backend URL: ${BACKEND_URL}"

# -------------------------------------------------------------
# 3. Deploy Service 2: Streamlit Dashboard
# -------------------------------------------------------------
echo "3. Building and deploying 'youtube-dashboard'..."
cp Dockerfile Dockerfile.backend
cp Dockerfile.dashboard Dockerfile

gcloud run deploy youtube-dashboard \
    --source . \
    --platform managed \
    --region "${REGION}" \
    --ingress all \
    --memory 1Gi \
    --cpu 1 \
    --min-instances 0 \
    --max-instances 5 \
    --set-env-vars "BACKEND_API_URL=${BACKEND_URL}/api" \
    --project "${PROJECT_ID}" \
    --allow-unauthenticated

cp Dockerfile.backend Dockerfile
rm -f Dockerfile.backend

DASHBOARD_URL=$(gcloud run services describe youtube-dashboard --region "${REGION}" --format="value(status.url)" --project "${PROJECT_ID}")

echo "=============================================================="
echo "🎉 Deployment successfully finished!"
echo "• Backend API:    ${BACKEND_URL}"
echo "• Dashboard UI:   ${DASHBOARD_URL}"
echo "• Code Sandbox:   ${SANDBOX_URL}"
echo "• Health Check:   curl -s ${BACKEND_URL}/health"
echo "• Setup Webhook:  curl -F 'url=${BACKEND_URL}/api/telegram/webhook' https://api.telegram.org/bot<TOKEN>/setWebhook"
echo "=============================================================="
