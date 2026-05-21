#!/bin/bash
set -e

# AR Co-Pilot Backend — quick start script

echo "AR Co-Pilot Backend"
echo "========================"

# Check Python
python --version 2>/dev/null || python3 --version

# Install dependencies if needed
if ! python -c "import fastapi" 2>/dev/null; then
  echo "Installing dependencies..."
  pip install -e ".[dev]" -q
fi

# Copy .env if missing
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

# Run migrations
echo "Running DB migrations..."
alembic upgrade head

# Seed data if DB is empty
DEAL_COUNT=$(python -c "
import sqlite3, sys
try:
    c = sqlite3.connect('ar_copilot.db').cursor()
    print(c.execute('SELECT COUNT(*) FROM deals').fetchone()[0])
except:
    print(0)
")
if [ "$DEAL_COUNT" -eq "0" ]; then
  echo "Seeding database..."
  python seed_data.py
fi

# Start server
echo ""
echo "Starting server on http://localhost:8000"
echo "API docs: http://localhost:8000/docs"
echo ""
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
