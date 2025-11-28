#!/bin/bash

echo "Stopping Celery Worker, Beat and Flower..."

pkill -f "celery -A portfolio_project worker"
pkill -f "celery -A portfolio_project beat"
pkill -f "celery -A portfolio_project flower"

echo "All Celery processes stopped."



# chmod +x stop_celery.sh
# ./stop_celery.sh
