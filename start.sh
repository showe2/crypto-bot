#!/usr/bin/env bash

set -e  # Exit on first error

# Go to the project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Check Python
if ! command -v python3 &> /dev/null; then
  echo "❌ python3 is not installed."
  exit 1
fi

# Create venv if missing
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Activate venv
echo "🔹 Activating virtual environment..."
# shellcheck source=/dev/null
source "$VENV_DIR/Scripts/activate"

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Setup env file if needed
if [ -f ".env.example" ] && [ ! -f ".env" ]; then
  echo "⚙️  Creating .env from example..."
  cp .env.example .env
  echo "Please update .env with your own settings."
fi

# Load environment variables from .env
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

# Default values if not in .env
HOST=${HOST:-localhost}
PORT=${PORT:-8000}

# Start the app
echo "🚀 Starting crypto-bot on http://$HOST:$PORT ..."
uvicorn app.main:app --reload --host "$HOST" --port "$PORT"
