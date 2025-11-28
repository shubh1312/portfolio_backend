Systemd unit examples for running Celery worker & beat (do not place these files under version control on production without editing).
Replace <USER>, <PROJECT_PATH>, and <VENV_PATH> with correct values for your system.

Example: /etc/systemd/system/portfolio_celery.service
```
[Unit]
Description=Celery Worker for portfolio_project
After=network.target

[Service]
Type=simple
User=<USER>
Group=<USER>
WorkingDirectory=<PROJECT_PATH>
Environment=PATH=<VENV_PATH>/bin
Environment=DJANGO_SETTINGS_MODULE=portfolio_project.settings
EnvironmentFile=<PROJECT_PATH>/.env
ExecStart=<VENV_PATH>/bin/celery -A portfolio_project worker --loglevel=info --concurrency=4
Restart=always

[Install]
WantedBy=multi-user.target
```

Example: /etc/systemd/system/portfolio_celery_beat.service
```
[Unit]
Description=Celery Beat for portfolio_project
After=network.target

[Service]
Type=simple
User=<USER>
Group=<USER>
WorkingDirectory=<PROJECT_PATH>
Environment=PATH=<VENV_PATH>/bin
Environment=DJANGO_SETTINGS_MODULE=portfolio_project.settings
EnvironmentFile=<PROJECT_PATH>/.env
ExecStart=<VENV_PATH>/bin/celery -A portfolio_project beat --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

After creating the files, run:
```
sudo systemctl daemon-reload
sudo systemctl enable portfolio_celery.service
sudo systemctl enable portfolio_celery_beat.service
sudo systemctl start portfolio_celery.service
sudo systemctl start portfolio_celery_beat.service
```

Notes:
- Ensure Redis is running and reachable by CELERY_BROKER_URL in .env.
