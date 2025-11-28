#!/bin/bash
set -euo pipefail

# ------------------------------------
#  CONFIGURATION
# ------------------------------------
VENV=".venv"
DJANGO_PORT=8000
FLOWER_PORT=5555
DEBUGPY_PORT=5678
PROJECT="portfolio_project"

# ------------------------------------
#  ACTIVATE VENV
# ------------------------------------
if [ ! -d "$VENV" ]; then
  echo "❌ Virtualenv '$VENV' not found!"
  exit 1
fi

source "$VENV/bin/activate"

# Create logs directory if missing
mkdir -p logs

echo ""
echo "============================================"
echo " 🚀 Starting ALL SERVERS (DEBUG MODE)"
echo "============================================"
echo ""

# ------------------------------------
#  START DJANGO
# ------------------------------------
echo "▶ Starting Django server on port $DJANGO_PORT ..."
python manage.py runserver $DJANGO_PORT > logs/django.log 2>&1 &
echo $! > logs/django.pid
echo "✔ Django PID: $(cat logs/django.pid)"

# ------------------------------------
#  START CELERY WORKER (DEBUG MODE)
# ------------------------------------
echo ""
echo "▶ Starting Celery Worker in DEBUG mode..."
export DEBUG_ATTACH=1
export DEBUGPY_PORT=$DEBUGPY_PORT

celery -A $PROJECT worker \
  -P solo \
  --concurrency=1 \
  --loglevel=INFO \
  > logs/worker.log 2>&1 &

echo $! > logs/celery_worker.pid
echo "✔ Celery Worker PID: $(cat logs/celery_worker.pid)"

# ------------------------------------
#  START CELERY BEAT
# ------------------------------------
echo ""
echo "▶ Starting Celery Beat..."
celery -A $PROJECT beat \
  --loglevel=INFO \
  > logs/beat.log 2>&1 &

echo $! > logs/celery_beat.pid
echo "✔ Celery Beat PID: $(cat logs/celery_beat.pid)"

# ------------------------------------
#  START FLOWER
# ------------------------------------
echo ""
echo "▶ Starting Flower on http://127.0.0.1:$FLOWER_PORT ..."
celery -A $PROJECT flower \
  --port=$FLOWER_PORT \
  --address=127.0.0.1 \
  > logs/flower.log 2>&1 &

echo $! > logs/flower.pid
echo "✔ Flower PID: $(cat logs/flower.pid)"

# ------------------------------------
#  SUMMARY
# ------------------------------------
echo ""
echo "============================================"
echo " ✅ All Servers Started in DEBUG Mode"
echo "============================================"
echo "🌐 Django       : http://127.0.0.1:$DJANGO_PORT"
echo "🌸 Flower       : http://127.0.0.1:$FLOWER_PORT"
echo ""
echo "📝 Logs directory: logs/"
echo ""
echo "📌 Attach VS Code debugger:"
echo "   Host: localhost"
echo "   Port: $DEBUGPY_PORT"
echo "============================================"
