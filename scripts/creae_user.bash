#!/usr/bin/env bash
set -e  # stop on error

# Run app with project root in PYTHONPATH
PYTHONPATH=$(pwd) .venv/bin/python ./scripts/create_user.py