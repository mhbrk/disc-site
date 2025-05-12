#!/bin/bash

set -euo pipefail

PROJECT_ID="breba-458921"
REGION="us-west1"
REPO_NAME="breba-repo"
SERVICE_NAME="breba-app"
IMAGE_URI="us-west1-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"
CHAT_AGENT_SERVICE="chat-agent"
PORT=8080

cp breba_app.Dockerfile Dockerfile

echo "🔨 Building and submitting breba-app..."
gcloud builds submit \
  --tag "${IMAGE_URI}" \
  --project "${PROJECT_ID}" \
  --timeout=30m

echo "🌐 Fetching chat-agent service URL..."
CHAT_AGENT_URL=$(gcloud run services describe "${CHAT_AGENT_SERVICE}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format="value(status.url)")

CHAT_URL=${CHAT_AGENT_URL}/chainlit/

echo "🚀 Deploying breba-app to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_URI}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --port "${PORT}" \
  --set-env-vars "CHAT_URL=${CHAT_URL}" \
  --project "${PROJECT_ID}"

echo "✅ Done. breba-app deployed with CHAT_URL=${CHAT_URL}"

rm Dockerfile