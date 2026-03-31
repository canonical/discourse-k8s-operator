#!/bin/bash
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Starts a LocalStack container scoped to S3 only, for integration tests.
#
# Two critical env vars fix the broken startup process:
#
#   IMAGE_NAME  - Without this, `localstack start` ignores any pre-pulled image and
#                 defaults to `localstack/localstack` (i.e. :latest), downloading it
#                 concurrently while the container is already running.  That competing
#                 download caused resource pressure that crashed the container in < 2 s.
#
#   SERVICES=s3 - Limits LocalStack to the S3 service only.  Starting all ~200 services
#                 by default requires 1+ GB RAM, exceeding self-hosted runner limits.

set -euo pipefail

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

# Remove any leftover container from a previous run on the same runner
docker rm -f localstack-main 2>/dev/null || true

# EDGE_BIND_HOST=0.0.0.0 ensures the gateway binds to all interfaces so
# K8s pods can reach LocalStack at 172.17.0.1:4566.
IMAGE_NAME="localstack/localstack:${LOCALSTACK_IMAGE_VERSION}" \
SERVICES=s3 \
EDGE_BIND_HOST=0.0.0.0 \
    localstack start -d

echo "Waiting for LocalStack to be ready..."
localstack wait -t 120
echo "LocalStack ready"
