#!/bin/bash

source .venv/bin/activate

celery -A portfolio_project worker --loglevel=info &
celery -A portfolio_project beat --loglevel=info &
celery -A portfolio_project flower --port=5555 --address=127.0.0.1 &



# chmod +x stop_celery.sh
# ./stop_celery.sh