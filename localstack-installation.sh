#!/bin/bash
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

sudo apt install python3.12-venv -y
VENV=$PWD/localstack-venv
python3 -m venv "$VENV"

export PATH=$VENV/bin:$PATH

pip install pip --upgrade
pip install pyopenssl --upgrade
pip install 'localstack>=1.4.0,<2.0.0' # install LocalStack cli
docker pull localstack/localstack # Make sure to pull the latest version of the image
EDGE_BIND_HOST=0.0.0.0 localstack start -d # Start LocalStack in the background (binding to all host ip)
echo "Waiting for LocalStack startup..."
# `localstack wait` (CLI 1.4.0) streams Docker logs looking for the exact string
# "Ready." (localstack/constants.py:READY_MARKER_OUTPUT). The current
# localstack/localstack:latest image is 3.x/4.x and no longer outputs that
# marker, so the log stream hits EOF in ~3 s and the CLI raises "Error: timeout"
# regardless of the -t value. Use a direct HTTP health-check loop instead.
timeout 120 bash -c 'until curl -sf http://localhost:4566/_localstack/health 2>/dev/null | grep -q "running\|\"health\""; do sleep 2; done'
echo "Startup complete"

