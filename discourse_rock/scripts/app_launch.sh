#!/bin/bash
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

export UNICORN_BIND_ALL=0.0.0.0
export UNICORN_SIDEKIQS=1

cd "$CONTAINER_APP_ROOT/app" || exit

bin/bundle exec prometheus_exporter &
bin/unicorn -c config/unicorn.conf.rb &

# If one of the processes exits, the other one will be killed so that the pod will be restarted by the failing probes
wait -n
kill "$(jobs -p)"
