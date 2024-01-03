#!/bin/bash
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

export UNICORN_BIND_ALL=0.0.0.0
export UNICORN_SIDEKIQS=1

cd "$CONTAINER_APP_ROOT/app" || exit
exec bin/unicorn -c config/unicorn.conf.rb
