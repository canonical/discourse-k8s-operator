#!/bin/bash

"${CONTAINER_APP_ROOT}/app/bin/bundle" exec rake --trace db:migrate
"${CONTAINER_APP_ROOT}/app/bin/bundle" exec rake assets:precompile 2>&1 | sed 's/^/asset-build: /'

if [ -n "${DISCOURSE_USE_S3}" ] && [ "${DISCOURSE_USE_S3}" == "true" ]; then
	echo "Running migration to S3..."
	"${CONTAINER_APP_ROOT}/app/bin/bundle" exec rake s3:upload_assets 2>&1
fi
