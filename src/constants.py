# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Constants for Discourse charm."""

import typing
from collections import defaultdict

DATABASE_NAME = "discourse"
DISCOURSE_PATH = "/srv/discourse/app"
THROTTLE_LEVELS: typing.Dict = defaultdict(dict)
THROTTLE_LEVELS["none"] = {
    "DISCOURSE_MAX_REQS_PER_IP_MODE": "none",
    "DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE": "false",
}
THROTTLE_LEVELS["permissive"] = {
    "DISCOURSE_MAX_REQS_PER_IP_MODE": "warn+block",
    "DISCOURSE_MAX_REQS_PER_IP_PER_MINUTE": "1000",
    "DISCOURSE_MAX_REQS_PER_IP_PER_10_SECONDS": "100",
    "DISCOURSE_MAX_USER_API_REQS_PER_MINUTE": "3000",
    "DISCOURSE_MAX_ASSET_REQS_PER_IP_PER_10_SECONDS": "400",
    "DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE": "false",
    "DISCOURSE_MAX_USER_API_REQS_PER_DAY": "30000",
    "DISCOURSE_MAX_ADMIN_API_REQS_PER_KEY_PER_MINUTE": "3000",
}
THROTTLE_LEVELS["strict"] = {
    "DISCOURSE_MAX_REQS_PER_IP_MODE": "block",
    "DISCOURSE_MAX_REQS_PER_IP_PER_MINUTE": "200",
    "DISCOURSE_MAX_REQS_PER_IP_PER_10_SECONDS": "50",
    "DISCOURSE_MAX_USER_API_REQS_PER_MINUTE": "100",
    "DISCOURSE_MAX_ASSET_REQS_PER_IP_PER_10_SECONDS": "200",
    "DISCOURSE_MAX_REQS_RATE_LIMIT_ON_PRIVATE": "false",
}
LOG_PATHS = [
    f"{DISCOURSE_PATH}/log/production.log",
    f"{DISCOURSE_PATH}/log/unicorn.stderr.log",
    f"{DISCOURSE_PATH}/log/unicorn.stdout.log",
]
MAX_CATEGORY_NESTING_LEVELS = [2, 3]
PROMETHEUS_PORT = 3000
REQUIRED_S3_SETTINGS = ["s3_access_key_id", "s3_bucket", "s3_region", "s3_secret_access_key"]
SCRIPT_PATH = "/srv/scripts"
SERVICE_NAME = "discourse"
CONTAINER_NAME = "discourse"
CONTAINER_APP_USERNAME = "_daemon_"
SERVICE_PORT = 3000
SETUP_COMPLETED_FLAG_FILE = "/run/discourse-k8s-operator/setup_completed"
DATABASE_RELATION_NAME = "database"
OAUTH_RELATION_NAME = "oauth"
OAUTH_SCOPE = "openid email"
