##!/usr/bin/env bash
#set -euo pipefail
#cd /opt/careerflow
#chown -R ubuntu:ubuntu /opt/careerflow
#runuser -u ubuntu -- python3 -m venv /opt/careerflow/backend/.venv
#runuser -u ubuntu -- /opt/careerflow/backend/.venv/bin/pip install --disable-pip-version-check -q -r /opt/careerflow/backend/requirements.txt
#mkdir -p /var/www/careerflow
#rm -rf /var/www/careerflow/*
#cp -a /opt/careerflow/frontend/dist/. /var/www/careerflow/
#chmod -R a+rX /var/www/careerflow
#systemctl daemon-reload
#systemctl enable --now careerflow.service
#systemctl restart careerflow.service
#systemctl restart caddy.service
#curl -fsS --retry 10 --retry-delay 3 http://127.0.0.1:8000/api/health




#!/usr/bin/env bash
set -euo pipefail

echo "========================================"
echo "Starting CareerFlow deployment..."
echo "========================================"

# 1. Navigate to the application directory
cd /opt/careerflow

# 2. Set application directory permissions
chown -R ubuntu:ubuntu /opt/careerflow

# 3. Create Python virtual environment
echo "Creating Python virtual environment..."

if [ ! -d /opt/careerflow/backend/.venv ]; then
    runuser -u ubuntu -- python3 -m venv \
        /opt/careerflow/backend/.venv
fi

# 4. Install Python dependencies
echo "Installing backend dependencies..."

runuser -u ubuntu -- \
    /opt/careerflow/backend/.venv/bin/pip install \
    --disable-pip-version-check \
    -q \
    -r /opt/careerflow/backend/requirements.txt

# 5. Deploy React frontend
echo "Deploying React frontend..."

mkdir -p /var/www/careerflow

rm -rf /var/www/careerflow/*

cp -a /opt/careerflow/frontend/dist/. \
    /var/www/careerflow/

chmod -R a+rX /var/www/careerflow

# 6. Reload systemd configuration
echo "Reloading systemd..."

systemctl daemon-reload

# 7. Enable and restart FastAPI
echo "Starting FastAPI backend..."

systemctl enable careerflow.service
systemctl restart careerflow.service

# 8. Restart Caddy web server
echo "Restarting Caddy..."

systemctl restart caddy.service

# 9. Wait for FastAPI readiness
echo "Waiting for FastAPI health check..."

if ! curl \
    --fail \
    --silent \
    --show-error \
    --retry 20 \
    --retry-connrefused \
    --retry-delay 3 \
    --max-time 5 \
    http://127.0.0.1:8000/api/health; then

    echo "ERROR: CareerFlow backend health check failed."

    echo "========================================"
    echo "FastAPI Service Status"
    echo "========================================"

    systemctl status careerflow.service \
        --no-pager -l || true

    echo "========================================"
    echo "FastAPI Recent Logs"
    echo "========================================"

    journalctl -u careerflow.service \
        -n 100 \
        --no-pager || true

    exit 1
fi

echo ""
echo "========================================"
echo "CareerFlow deployed successfully!"
echo "========================================"
