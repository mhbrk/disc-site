#!/usr/bin/env bash
set -e  # stop on error

echo "Create a user for your local instance of Breba"
# Run app with project root in PYTHONPATH
PYTHONPATH=$(pwd) .venv/bin/python ./scripts/create_user.py