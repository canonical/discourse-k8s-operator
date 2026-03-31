#!/bin/bash
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Sets up MicroCeph with RADOS Gateway (radosgw) as an S3-compatible object
# store for integration tests.
#
# MicroCeph is a Canonical-maintained snap — no third-party container images
# required.  radosgw provides a full S3-compatible API and supports
# virtual-hosted bucket routing via rgw_dns_name, matching the pattern that
# Discourse uses: {bucket}.s3.localhost.localstack.cloud.

set -euo pipefail

S3_ACCESS_KEY="my-lovely-key"
S3_SECRET_KEY="this-is-very-secret"
S3_BUCKET="tests"

sudo snap install microceph
sudo microceph cluster bootstrap
sudo microceph disk add loop,4G,1

# Configure virtual-hosted routing BEFORE enabling RGW so the daemon starts
# with the right setting.  Requests to {bucket}.s3.localhost.localstack.cloud
# are then routed to the correct bucket without any path-style workarounds.
sudo microceph.ceph config set client.rgw rgw_dns_name s3.localhost.localstack.cloud

sudo microceph enable rgw

# Create CI user with credentials expected by generate_s3_config() in tests.
sudo microceph.radosgw-admin user create \
    --uid ci-user \
    --display-name "CI User" \
    --access-key "${S3_ACCESS_KEY}" \
    --secret-key "${S3_SECRET_KEY}"

# Determine the host IP reachable from K8s pods (same IP as --s3-address).
HOST_IP=$(ip -4 route get 2.2.2.2 | awk 'NR==1{print $7}')
echo "S3 host IP: ${HOST_IP}"

# Wait for radosgw to respond (403 = running but unauthenticated; that is fine).
echo "Waiting for radosgw to be ready..."
timeout 120 bash -c \
    "until curl -s -o /dev/null -w '%{http_code}' http://${HOST_IP} | grep -qE '^(200|403)'; do sleep 2; done"
echo "radosgw ready"

# Pre-create the test bucket using boto3 (available via pip, no extra snap needed).
# Unlike LocalStack, radosgw does not auto-create buckets on first access.
pip3 install --quiet boto3
python3 - <<EOF
import boto3, sys

s3 = boto3.client(
    "s3",
    region_name="us-east-1",
    aws_access_key_id="${S3_ACCESS_KEY}",
    aws_secret_access_key="${S3_SECRET_KEY}",
    endpoint_url="http://${HOST_IP}",
)
s3.create_bucket(Bucket="${S3_BUCKET}")
print(f"Bucket '${S3_BUCKET}' created")
EOF
