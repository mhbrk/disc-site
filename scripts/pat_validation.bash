#!/usr/bin/env bash
set -euo pipefail

# Only set ENV_FILE if not already set
: "${ENV_FILE:=.env}"
touch "$ENV_FILE"
echo "Using ENV_FILE=$ENV_FILE"

# ---------------------------------------
# Check for existing token at the beginning
# ---------------------------------------
if grep -q '^GITHUB_PERSONAL_ACCESS_TOKEN=' "$ENV_FILE" 2>/dev/null; then
  warn "GITHUB_PERSONAL_ACCESS_TOKEN already present in ${ENV_FILE}."
  read -r -p "Do you want to replace it? [y/N] " ans
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    warn "Proceeding to replace existing token."
    # fall through → continue script (will prompt for new token, validate, and overwrite later)
  else
    ok "Keeping existing token. Exiting."
    exit 0
  fi
fi


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
TOKEN=""
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

# Write or override token in .env
if grep -q '^GITHUB_PERSONAL_ACCESS_TOKEN=' "$ENV_FILE" 2>/dev/null; then
  # Replace the existing line
  sed -i "s|^GITHUB_PERSONAL_ACCESS_TOKEN=.*|GITHUB_PERSONAL_ACCESS_TOKEN=${TOKEN}|" "$ENV_FILE"
  ok "Replaced token in ${ENV_FILE}"
else
  # Append new line
  echo "GITHUB_PERSONAL_ACCESS_TOKEN=${TOKEN}" >> "$ENV_FILE"
  ok "Saved token to ${ENV_FILE}"
fi
