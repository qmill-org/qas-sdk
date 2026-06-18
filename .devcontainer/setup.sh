#!/usr/bin/env bash
set -euo pipefail

echo "Setting up qas-sdk development environment..."
python -m pip install --upgrade pip
pip install -e .[dev] pre-commit build twine

pre-commit install --hook-type pre-commit

echo "Setup complete."
