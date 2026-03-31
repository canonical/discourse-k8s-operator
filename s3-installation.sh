#!/bin/bash
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.
#
# Sets up MicroCeph radosgw as an S3-compatible store for integration tests.

set -euo pipefail

S3_ACCESS_KEY="my-lovely-key"
S3_SECRET_KEY="this-is-very-secret"
S3_BUCKET="tests"

sudo snap install microceph
sudo microceph cluster bootstrap
sudo microceph disk add loop,1G,3

timeout 180 bash -c \
    'until sudo microceph.ceph health 2>/dev/null | grep -qE "^HEALTH_OK|^HEALTH_WARN"; do sleep 3; done'

sudo microceph enable rgw

timeout 120 bash -c \
    'until sudo microceph.ceph status 2>/dev/null | grep -q "rgw:"; do sleep 3; done'

sudo microceph.radosgw-admin user create \
    --uid ci-user \
    --display-name "CI User" \
    --access-key "${S3_ACCESS_KEY}" \
    --secret-key "${S3_SECRET_KEY}"

# Patch port 80 → 7480 (avoids conflict with microk8s nginx ingress on port 80)
# and inject rgw_dns_name for virtual-hosted bucket routing.
sudo sed -i \
    -e 's/beast port=80/beast port=7480/' \
    -e '/rgw frontends/a rgw dns name = s3.localhost.localstack.cloud' \
    /var/snap/microceph/current/conf/radosgw.conf
sudo snap restart microceph.rgw

timeout 120 bash -c \
    "until curl --max-time 5 -s -o /dev/null -w '%{http_code}' http://127.0.0.1:7480 | grep -qE '^(200|403)'; do sleep 2; done"

curl -sf -X PUT "http://127.0.0.1:7480/${S3_BUCKET}" \
    --aws-sigv4 "aws:amz:us-east-1:s3" \
    --user "${S3_ACCESS_KEY}:${S3_SECRET_KEY}"
