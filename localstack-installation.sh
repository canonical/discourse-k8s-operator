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
echo "Waiting for LocalStack startup..." # Wait 30 seconds for the LocalStack container
localstack wait -t 30 # to become ready before timing out 
echo "Startup complete"

