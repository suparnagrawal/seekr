#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "Syncing dependencies in backend..."
cd backend
uv sync --frozen

echo "Build complete!"
