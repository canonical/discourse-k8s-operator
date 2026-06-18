#!/bin/bash
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

set -euo pipefail

S3_ACCESS_KEY="my-lovely-key"
S3_SECRET_KEY="this-is-very-secret"
S3_BUCKET="tests"

sudo snap install microceph
sudo microceph cluster bootstrap
sudo microceph disk add loop,1G,3
sudo microceph enable rgw --port 7480 --wait
sudo microceph.ceph config set client rgw_dns_name s3.localhost.localstack.cloud

sudo snap restart microceph.rgw

curl --connect-timeout 2 --max-time 3 --retry 5 --retry-delay 2 --retry-connrefused -s http://127.0.0.1:7480 > /dev/null && echo "Success!" || echo "Failed after 5 attempts."

sudo microceph.radosgw-admin user create --uid ci-user --display-name "CI User" --access-key "${S3_ACCESS_KEY}" --secret-key "${S3_SECRET_KEY}"

# Create bucket
curl -sf -X PUT "http://127.0.0.1:7480/${S3_BUCKET}" --aws-sigv4 "aws:amz:us-east-1:s3" --user "${S3_ACCESS_KEY}:${S3_SECRET_KEY}"
