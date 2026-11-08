#!/usr/bin/env bash
set -euo pipefail
cd /opt/careerflow
chown -R ubuntu:ubuntu /opt/careerflow
runuser -u ubuntu -- python3 -m venv /opt/careerflow/backend/.venv
runuser -u ubuntu -- /opt/careerflow/backend/.venv/bin/pip install --disable-pip-version-check -q -r /opt/careerflow/backend/requirements.txt
mkdir -p /var/www/careerflow
rm -rf /var/www/careerflow/*
cp -a /opt/careerflow/frontend/dist/. /var/www/careerflow/
chmod -R a+rX /var/www/careerflow
systemctl daemon-reload
systemctl enable --now careerflow.service
systemctl restart careerflow.service
systemctl restart caddy.service
curl -fsS --retry 10 --retry-delay 3 http://127.0.0.1:8000/api/health
