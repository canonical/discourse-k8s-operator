#!/bin/bash
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

export UNICORN_BIND_ALL=0.0.0.0
export UNICORN_SIDEKIQS=1

su -s /bin/bash -c "${CONTAINER_APP_ROOT}/app/bin/bundle exec prometheus_exporter -b 0.0.0.0" &
su -s /bin/bash -c "${CONTAINER_APP_ROOT}/app/bin/unicorn -c ${CONTAINER_APP_ROOT}/app/config/unicorn.conf.rb" "${CONTAINER_APP_USERNAME}" &

# If one of the processes exits, the other one will be killed so that the pod will be restarted by the failing probes
wait -n
kill "$(jobs -p)"
