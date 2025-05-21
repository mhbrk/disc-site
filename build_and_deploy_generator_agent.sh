#!/bin/bash

set -euo pipefail

PROJECT_ID="breba-458921"
REGION="us-west1"
REPO_NAME="breba-repo"
SERVICE_NAME="generator-agent"
IMAGE_URI="us-west1-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"
PORT=8080

cp generator_agent.Dockerfile Dockerfile

echo "🔨 Building and submitting generator-agent..."
gcloud builds submit \
  --tag "${IMAGE_URI}" \
  --project "${PROJECT_ID}" \
  --timeout=30m


echo "🚀 Deploying generator-agent to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_URI}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --port "${PORT}" \
  --project "${PROJECT_ID}"

echo "✅ Done. generator-agent deployed"

rm Dockerfile