#!/bin/bash
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

sudo apt install python3.12-venv -y
VENV=$PWD/localstack-venv
python3 -m venv "$VENV"

export PATH=$VENV/bin:$PATH

pip install pip --upgrade
pip install pyopenssl --upgrade

# renovate: datasource=pypi depName=localstack
LOCALSTACK_CLI_VERSION="4.9.2"
# renovate: datasource=docker depName=localstack/localstack
LOCALSTACK_IMAGE_VERSION="4.9.2"
pip install "localstack==${LOCALSTACK_CLI_VERSION}"
docker pull "localstack/localstack:${LOCALSTACK_IMAGE_VERSION}"
EDGE_BIND_HOST=0.0.0.0 localstack start -d # Start LocalStack in the background (binding to all host ip)
echo "Waiting for LocalStack startup..."
localstack wait -t 60
echo "Startup complete"

