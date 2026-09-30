#!/usr/bin/env bash
set -e

echo "=== Starting YouTube Analytics Platform (Dev Mode) ==="

# Trap INT and TERM to kill child processes cleanly
trap 'kill 0' EXIT

# Start FastAPI backend
echo "Starting FastAPI backend on http://localhost:8000..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &

# Start Streamlit dashboard
echo "Starting Streamlit dashboard on http://localhost:8501..."
streamlit run "dashboard/0_🏠_Главная.py" --server.port 8501 --server.headless true &

wait
