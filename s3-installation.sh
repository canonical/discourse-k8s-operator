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

# Determine the host IP reachable from K8s pods (same IP as --s3-address).
HOST_IP=$(ip -4 route get 2.2.2.2 | awk 'NR==1{print $7}')
echo "S3 host IP: ${HOST_IP}"

sudo snap install microceph
sudo microceph cluster bootstrap

# Three 1 GB loop disks (matching the Kyuubi reference setup).
# MicroCeph needs at least one OSD before it will mark the cluster HEALTH_OK.
sudo microceph disk add loop,1G,3

# Wait for the Ceph cluster to reach a usable health state before issuing any
# admin commands.  Without this gate, radosgw-admin hangs indefinitely because
# the monitors are not yet ready to serve requests.
echo "Waiting for Ceph cluster health..."
timeout 180 bash -c \
    'until sudo microceph.ceph health 2>/dev/null | grep -qE "^HEALTH_OK|^HEALTH_WARN"; do sleep 3; done'
echo "Ceph cluster healthy"

sudo microceph enable rgw

# Wait for radosgw to register with the Ceph cluster monitors — this is the
# reliable readiness signal for admin operations.  HTTP port 80 may come up
# later; `ceph status` tracks the daemon registration, not the HTTP listener.
echo "Waiting for radosgw to register with cluster..."
timeout 120 bash -c \
    'until sudo microceph.ceph status 2>/dev/null | grep -q "rgw:"; do sleep 3; done'
echo "radosgw registered"

# Create CI user.  Safe to run now that the Ceph monitors report radosgw up.
sudo microceph.radosgw-admin user create \
    --uid ci-user \
    --display-name "CI User" \
    --access-key "${S3_ACCESS_KEY}" \
    --secret-key "${S3_SECRET_KEY}"

# Configure virtual-hosted routing and restart the daemon to apply it.
sudo microceph.ceph config set client.rgw rgw_dns_name s3.localhost.localstack.cloud
sudo snap restart microceph.radosgw

# Wait for the HTTP listener to come back after restart.  Use --max-time to
# prevent curl from hanging when radosgw accepts the connection but is not yet
# sending responses (which blocked the loop in the previous iteration).
echo "Waiting for radosgw HTTP..."
timeout 120 bash -c \
    "until curl --max-time 5 -s -o /dev/null -w '%{http_code}' http://${HOST_IP} | grep -qE '^(200|403)'; do sleep 2; done"
echo "radosgw ready"

# Pre-create the test bucket.  radosgw does not auto-create buckets on first access.
pip3 install --quiet boto3
python3 - <<EOF
import boto3

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
