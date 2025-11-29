#!/bin/bash
set -euo pipefail

LOG_DIR="logs"

echo ""
echo "============================================"
echo " 🛑 FORCE STOPPING ALL SERVERS + CHILDREN"
echo "============================================"
echo ""

# Kill by PID files (your original logic)
stop_by_pid() {
    local name="$1"
    local pid_file="$LOG_DIR/$2"

    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")

        if ps -p "$pid" > /dev/null 2>&1; then
            echo "▶ Killing $name (PID $pid)..."
            kill -TERM "$pid" || true
            sleep 2

            # Force kill
            if ps -p "$pid" > /dev/null 2>&1; then
                echo "⚠ Force killing $name..."
                kill -9 "$pid" || true
            fi
        fi
        rm -f "$pid_file"
    fi
}

# NEW: Kill ALL processes by command name (catches orphans)
kill_by_command() {
    local name="$1"
    echo "🔪 Killing all '$name' processes..."
    pkill -f "$name" -TERM || true
    sleep 2
    pkill -f "$name" -9 || true
    echo "✔ $name processes terminated."
}

mkdir -p "$LOG_DIR"

# 1. Kill by PID files first
stop_by_pid "Django" "django.pid"
stop_by_pid "Celery Worker" "celery_worker.pid" 
stop_by_pid "Celery Beat" "celery_beat.pid"
stop_by_pid "Flower" "flower.pid"

# 2. Kill ALL remaining processes by command
echo "=== TERMINATING ORPHAN PROCESSES ==="
kill_by_command "runserver"
kill_by_command "celery.*worker"
kill_by_command "celery.*beat" 
kill_by_command "celery.*flower"
kill_by_command "python.*manage.py"
kill_by_command "flower"

# 3. Kill by ports (nuclear option)
echo "=== KILLING BY PORTS ==="
lsof -ti:8000 | xargs kill -9 || true    # Django
lsof -ti:5555 | xargs kill -9 || true    # Flower
lsof -ti:5678 | xargs kill -9 || true    # Debugpy

echo "============================================"
echo " ✅ ALL PROCESSES TERMINATED"
echo "============================================"
