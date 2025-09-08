#!/usr/bin/env bash
set -e  # Exit on error

MONGO_CONTAINER="breba-mongo"
MONGO_PORT=27017
MONGO_DB="breba-dev"
MONGO_IMAGE="mongo:8.0"   # Pin to MongoDB 8.0 release
ENV_FILE="./breba_app/.env"

# Ensure ENV_FILE exists
touch "$ENV_FILE"

# Check if OPENAI_API_KEY is already in file
if ! grep -q '^OPENAI_API_KEY=' "$ENV_FILE"; then
  read -r -p "OpenAI API Key: " OPENAI_API_KEY
  echo "OPENAI_API_KEY=$OPENAI_API_KEY" >> "$ENV_FILE"
  echo "✅ Added OPENAI_API_KEY to $ENV_FILE"
else
  echo "ℹ️ OPENAI_API_KEY already exists in $ENV_FILE, skipping..."
fi

echo "=== Setting up local MongoDB with Docker ==="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
  echo "❌ Docker not found. Please install Docker first."
  exit 1
fi

# Start Mongo container if not running
if [ ! "$(docker ps -q -f name=$MONGO_CONTAINER)" ]; then
  if [ "$(docker ps -aq -f status=exited -f name=$MONGO_CONTAINER)" ]; then
    echo "Starting existing MongoDB container..."
    docker start $MONGO_CONTAINER
  else
    echo "Creating new MongoDB container with image $MONGO_IMAGE..."
    docker run -d \
      --name $MONGO_CONTAINER \
      -p $MONGO_PORT:27017 \
      -v "$(pwd)/mongo-data:/data/db" \
      $MONGO_IMAGE
  fi
else
  echo "MongoDB container already running."
fi

# Wait until Mongo is ready
echo "Waiting for MongoDB to be ready..."
until docker exec $MONGO_CONTAINER mongosh --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
  sleep 1
done

echo "✅ MongoDB is running on localhost:$MONGO_PORT"

# Add MONGO_URI to .env if missing
if ! grep -q "MONGO_URI" "$ENV_FILE" 2>/dev/null; then
  echo "Adding MONGO_URI to $ENV_FILE"
  echo "MONGO_URI=mongodb://localhost:$MONGO_PORT/$MONGO_DB" >> "$ENV_FILE"
else
  echo "MONGO_URI already present in $ENV_FILE"
fi

echo "👉 Your local MONGO_URI is: mongodb://localhost:$MONGO_PORT/$MONGO_DB"

echo "=== Setting up Chainlit environment ==="
echo "========================================"
# Check if .venv exists
if [ ! -d ".venv" ]; then
  echo ".venv not found. Creating virtual environment..."
  python3 -m venv .venv
  echo "Installing requirements..."
  .venv/bin/pip install --upgrade pip
  if [ -f requirements.txt ]; then
    .venv/bin/pip install -r requirements.txt
  fi
fi

# Ensure Chainlit is installed (in case it's not in requirements.txt yet)
.venv/bin/pip install --quiet chainlit

# Generate CHAINLIT_AUTH_SECRET if missing
if ! grep -q "CHAINLIT_AUTH_SECRET" "$ENV_FILE" 2>/dev/null; then
  echo "Generating CHAINLIT_AUTH_SECRET..."
  SECRET=$(.venv/bin/chainlit create-secret | grep CHAINLIT_AUTH_SECRET | cut -d= -f2- | tr -d '"')
  echo "CHAINLIT_AUTH_SECRET=$SECRET" >> $ENV_FILE
  echo "Added CHAINLIT_AUTH_SECRET to .env"
fi

echo "Environment is ready. Activate with: source .venv/bin/activate"


# Verify GitHub PAT
source ./scripts/pat_validation.bash

# Creating User
source ./scripts/create_user.bash

echo "CLOUDFLARE_ENDPOINT=https://c0e7f083e56fe64be2af84fa3f82e689.r2.cloudflarestorage.com" >> "$ENV_FILE"
echo "USERS_BUCKET=dev-breba-users" >> "$ENV_FILE"
echo "PUBLIC_BUCKET=breba-public" >> "$ENV_FILE"
echo "CDN_BASE_URL=https://dev-cdn.breba.app" >> "$ENV_FILE"

ok "Done."
