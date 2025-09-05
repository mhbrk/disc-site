#!/usr/bin/env bash
set -e  # Exit on error

# Go to the script's directory (project root)
cd "$(dirname "$0")"

MONGO_CONTAINER="breba-mongo"
MONGO_PORT=27017
MONGO_DB="breba-dev"
MONGO_IMAGE="mongo:8.0"   # Pin to MongoDB 8.0 release
ENV_FILE=".env"

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
if ! grep -q "CHAINLIT_AUTH_SECRET" .env 2>/dev/null; then
  echo "Generating CHAINLIT_AUTH_SECRET..."
  SECRET=$(.venv/bin/chainlit create-secret)
  echo "CHAINLIT_AUTH_SECRET=$SECRET" >> .env
  echo "Added CHAINLIT_AUTH_SECRET to .env"
fi

echo "Environment is ready. Activate with: source .venv/bin/activate"



echo "=== Setting up GitHub PAT ==="
echo "Instructions:"
echo "1. Go to https://github.com/settings/personal-access-tokens/new and create a personal access token without expiration"


# -------- Config you can edit --------
REQUIRED_SCOPES=("repo" "workflow" "read:org")   # classic PAT scopes you require

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
warn() { printf "⚠️  %s\n" "$*"; }
ok()   { printf "✅ %s\n" "$*"; }
fail() { printf "❌ %s\n" "$*"; exit 1; }

# Ensure curl present
command -v curl >/dev/null || fail "curl not found"

# Read token from env or prompt
TOKEN="${GITHUB_PERSONAL_ACCESS_TOKEN:-}"
if [ -z "${TOKEN}" ]; then
  read -r -s -p "Paste your GitHub token (input hidden): " TOKEN
  echo
fi
[ -n "${TOKEN}" ] || fail "No token provided."

bold "Checking token…"

# Hit /user to confirm token is valid and capture headers
# -s silent, -D - dump headers to stdout, -o /dev/null discard body
HEADERS="$(curl -s -D - -o /dev/null -H "Authorization: token ${TOKEN}" https://api.github.com/user || true)"
STATUS="$(printf "%s" "$HEADERS" | head -n1 | awk '{print $2}')"

if [ "$STATUS" != "200" ]; then
  printf "%s\n" "$HEADERS" | head -n1
  fail "Token did not authenticate (HTTP $STATUS)."
fi
ok "Token is valid."

# Extract classic PAT scopes if present
SCOPES_LINE="$(printf "%s" "$HEADERS" | tr -d '\r' | grep -i '^x-oauth-scopes:' || true)"
SCOPES="$(printf "%s" "$SCOPES_LINE" | cut -d' ' -f2- | tr -d ' ' )" # comma-separated, no spaces

if [ -n "$SCOPES" ]; then
  # Classic PAT path
  ok "Detected classic PAT."
  IFS=',' read -r -a HAVE <<< "$SCOPES"

  # Check required scopes
  MISSING=()
  for req in "${REQUIRED_SCOPES[@]}"; do
    FOUND="no"
    for have in "${HAVE[@]}"; do
      if [ "$req" = "$have" ]; then FOUND="yes"; break; fi
    done
    [ "$FOUND" = "yes" ] || MISSING+=("$req")
  done

  if [ ${#MISSING[@]} -gt 0 ]; then
    warn "Token is missing required scopes: ${MISSING[*]}"
    echo "Required scopes are: ${REQUIRED_SCOPES[*]}"
    fail "Please regenerate your token with the missing scopes."
  else
    ok "Required scopes present: ${REQUIRED_SCOPES[*]}"
  fi
else
  # Fine-grained PAT path (no x-oauth-scopes header)
  ok "Detected fine-grained token (no classic scopes header)."
  read -r -p "Enter a GitHub repo URL to test access (e.g. https://github.com/owner/repo): " REPO_URL
  if [[ ! "$REPO_URL" =~ ^https://github.com/([^/]+)/([^/]+)$ ]]; then
    fail "Invalid URL format. Must be like: https://github.com/owner/repo"
  fi
  OWNER="${BASH_REMATCH[1]}"
  REPO="${BASH_REMATCH[2]}"

  RSTATUS="$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: token ${TOKEN}" \
    "https://api.github.com/repos/${OWNER}/${REPO}")"

  if [ "$RSTATUS" != "200" ]; then
    fail "Fine-grained token cannot read ${OWNER}/${REPO} (HTTP $RSTATUS). Adjust repo/permissions when creating the token."
  else
    ok "Token can access ${OWNER}/${REPO}."
  fi
fi

# Write to .env if missing
if ! grep -q '^GITHUB_PERSONAL_ACCESS_TOKEN=' "$ENV_FILE" 2>/dev/null; then
  echo "GITHUB_PERSONAL_ACCESS_TOKEN=${TOKEN}" >> "$ENV_FILE"
  ok "Saved token to ${ENV_FILE}"
else
  warn "GITHUB_PERSONAL_ACCESS_TOKEN already present in ${ENV_FILE} (not overwritten)."
fi

ok "Done."
