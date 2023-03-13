#!/bin/bash

"${CONTAINER_APP_ROOT}/app/bin/bundle" exec rake --trace db:migrate
