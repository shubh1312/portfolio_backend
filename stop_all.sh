#!/bin/bash
set -euo pipefail

LOG_DIR="logs"

echo ""
echo "============================================"
echo " 🛑 STOPPING ALL SERVERS "
echo "============================================"
echo ""

stop_process() {
    local name="$1"
    local pid_file="$LOG_DIR/$2"

    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")

        if ps -p "$pid" > /dev/null 2>&1; then
            echo "▶ Stopping $name (PID $pid)..."
            kill "$pid" || true
            sleep 1

            # Force kill if still alive
            if ps -p "$pid" > /dev/null 2>&1; then
                echo "⚠ $name did not stop, forcing kill -9..."
                kill -9 "$pid" || true
            fi

            echo "✔ $name stopped."
        else
            echo "⚠ $name PID file exists but process not running. Cleaning PID file."
        fi

        rm -f "$pid_file"
    else
        echo "ℹ No PID file for $name ($pid_file not found). Skipping."
    fi

    echo ""
}

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

stop_process "Django" "django.pid"
stop_process "Celery Worker" "celery_worker.pid"
stop_process "Celery Beat" "celery_beat.pid"
stop_process "Flower" "flower.pid"

echo "============================================"
echo " ✅ All services stopped."
echo "============================================"
echo ""
