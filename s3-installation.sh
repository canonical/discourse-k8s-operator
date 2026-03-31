#!/bin/bash
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Sets up MicroCeph radosgw as an S3-compatible store for integration tests.

set -euo pipefail

S3_ACCESS_KEY="my-lovely-key"
S3_SECRET_KEY="this-is-very-secret"
S3_BUCKET="tests"

# Host IP reachable from K8s pods — passed to tests as --s3-address.
HOST_IP=$(ip -4 route get 2.2.2.2 | awk 'NR==1{print $7}')
echo "S3 host IP: ${HOST_IP}"

sudo snap install microceph
sudo microceph cluster bootstrap
sudo microceph disk add loop,1G,3

echo "Waiting for Ceph cluster health..."
timeout 180 bash -c \
    'until sudo microceph.ceph health 2>/dev/null | grep -qE "^HEALTH_OK|^HEALTH_WARN"; do sleep 3; done'
echo "Ceph cluster healthy"

# Set before enabling RGW so the daemon reads it at startup.
sudo microceph.ceph config set client.rgw rgw_dns_name s3.localhost.localstack.cloud

sudo microceph enable rgw

# Use ceph status (not HTTP) as the readiness gate — radosgw-admin talks to
# the Ceph monitors, not the HTTP listener.
echo "Waiting for radosgw to register with cluster..."
timeout 120 bash -c \
    'until sudo microceph.ceph status 2>/dev/null | grep -q "rgw:"; do sleep 3; done'
echo "radosgw registered"

sudo microceph.radosgw-admin user create \
    --uid ci-user \
    --display-name "CI User" \
    --access-key "${S3_ACCESS_KEY}" \
    --secret-key "${S3_SECRET_KEY}"

# 403 = running but unauthenticated; --max-time prevents curl hanging on a
# slow-to-respond listener.
echo "Waiting for radosgw HTTP..."
timeout 120 bash -c \
    "until curl --max-time 5 -s -o /dev/null -w '%{http_code}' http://${HOST_IP} | grep -qE '^(200|403)'; do sleep 2; done"
echo "radosgw ready"

echo "Creating bucket ${S3_BUCKET}..."
curl -sf -X PUT "http://${HOST_IP}/${S3_BUCKET}" \
    --aws-sigv4 "aws:amz:us-east-1:s3" \
    --user "${S3_ACCESS_KEY}:${S3_SECRET_KEY}"
echo "Bucket '${S3_BUCKET}' created"
