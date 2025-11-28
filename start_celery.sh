#!/bin/bash
set -euo pipefail

source .venv/bin/activate

mkdir -p logs pids

# Worker
celery -A portfolio_project worker --loglevel=info \
  > logs/worker.log 2>&1 &
echo $! > pids/celery_worker.pid
echo "Started worker (pid $(cat pids/celery_worker.pid))"

# Beat
celery -A portfolio_project beat --loglevel=info \
  > logs/beat.log 2>&1 &
echo $! > pids/celery_beat.pid
echo "Started beat (pid $(cat pids/celery_beat.pid))"

# Flower (only if port free)
PORT=5555
if lsof -i :$PORT >/dev/null 2>&1; then
  echo "Port $PORT already in use — skipping Flower start."
else
  celery -A portfolio_project flower --port=$PORT --address=127.0.0.1 \
    > logs/flower.log 2>&1 &
  echo $! > pids/flower.pid
  echo "Started Flower (pid $(cat pids/flower.pid))"
fi

echo "Done. Tail logs with: tail -f logs/worker.log"
