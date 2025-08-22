#!/usr/bin/env bash
set -e  # stop on error

# Go to the script's directory (project root)
cd "$(dirname "$0")"

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

echo "Starting app..."
# Run app with project root in PYTHONPATH
PYTHONPATH=$(pwd) .venv/bin/python breba_app/main.py