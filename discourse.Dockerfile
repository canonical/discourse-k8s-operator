FROM ubuntu:focal

# ARGS become environment variables, but can be overridden using the
# --build-arg var=foo option to docker build. This allows you to have a
# default build image, but customize certain options such as app version or
# userids, etc.
ARG CONTAINER_APP_VERSION
ARG CONTAINER_APP_USERNAME
ARG CONTAINER_APP_UID
ARG CONTAINER_APP_GROUP
ARG CONTAINER_APP_GID

# Used in Launchpad OCI Recipe build to tag the image.
LABEL org.label-schema.version=${CONTAINER_APP_VERSION:-v2.7.10}

# Copy any args we got into the environment.
ENV CONTAINER_APP_VERSION ${CONTAINER_APP_VERSION:-v2.7.10}
ENV CONTAINER_APP_USERNAME ${CONTAINER_APP_USERNAME:-discourse}
ENV CONTAINER_APP_UID ${CONTAINER_APP_UID:-200}
ENV CONTAINER_APP_GROUP ${CONTAINER_APP_GROUP:-discourse}
ENV CONTAINER_APP_GID ${CONTAINER_APP_GID:-200}

# CONTAINER_APP_ROOT is where files related to this application go.
ENV CONTAINER_APP_ROOT=/srv/discourse
ENV GEM_HOME ${CONTAINER_APP_ROOT}/.gem

# We don't want packages prompting us during install.
ENV DEBIAN_FRONTEND=noninteractive

RUN ln -s /usr/share/zoneinfo/UTC /etc/localtime \
    && addgroup --gid "${CONTAINER_APP_GID}" "${CONTAINER_APP_GROUP}" \
    && adduser --uid "${CONTAINER_APP_UID}" --home "${CONTAINER_APP_ROOT}" --gid "${CONTAINER_APP_GID}" --system "${CONTAINER_APP_USERNAME}" \
    && apt-get update \
    && apt-get install -y brotli \
    gettext-base \
    gifsicle \
    git \
    imagemagick \
    jhead \
    jpegoptim \
    libjpeg-turbo-progs \
    libpq-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    libz-dev \
    uglifyjs.terser \
    node-uglify \
    optipng \
    pngquant \
    postgresql-client \
    postgresql-client-common \
    redis-tools \
    ruby2.7 \
    ruby2.7-dev \
    tzdata \
    ubuntu-dev-tools \
    zlib1g-dev \
    && rm /var/lib/apt/lists/* \
# Older versions of the uglifyjs.terser package install a uglifyjs.terser
# command but not the terser command, terser command exists in $PATH is
# vital to trigger js assets compression using node. Manually create the
# terser command if it does not exist. Please remove this line if the
# base image is >= 22.04. Also, please consider removing the node-uglify
# when upgrading to discourse >= 2.8.0, since the node-uglify is not
# required to trigger node js assets compression, only terser will do fine.
    && which terser || ln -s $(which uglifyjs.terser) /usr/local/bin/terser \
# Run build process.
    && git -C "${CONTAINER_APP_ROOT}" clone --depth 1 --branch "${CONTAINER_APP_VERSION}" https://github.com/discourse/discourse.git app

# Apply patch for LP#1903695
COPY image/patches /srv/patches
RUN git -C "${CONTAINER_APP_ROOT}/app" apply /srv/patches/lp1903695.patch \
    && rm -rf /srv/patches \
    && mkdir -p "${CONTAINER_APP_ROOT}/.gem" \
# Create the backup and upload directories as Discourse doesn't like it 
# when they are missing and won't auto-create them at runtime
    && mkdir -p "${CONTAINER_APP_ROOT}/app/tmp/backups/default" \
    && mkdir -p "${CONTAINER_APP_ROOT}/app/public/backups/default" \
    && mkdir -p "${CONTAINER_APP_ROOT}/app/public/uploads/default" \
    && chown -R "${CONTAINER_APP_USERNAME}:${CONTAINER_APP_GROUP}" "${CONTAINER_APP_ROOT}" \
# This must be done as the discourse user in order to avoid permission 
# problems later.
    && su -s /bin/bash -c 'gem install bundler' "${CONTAINER_APP_USERNAME}" \
    && su -s /bin/bash -c '${CONTAINER_APP_ROOT}/app/bin/bundle install' "${CONTAINER_APP_USERNAME}" \
# If intermediate files are generated by the build process or other files are
# generated that are not needed at runtime, remove them here to save image size.
# If we don't do this they will become part of the image even if removed later.
    && find "${CONTAINER_APP_ROOT}" -name tmp -type d -exec rm -rf {} + \
    && apt-get autoremove \
    && apt-get clean

# Copy run-time scripts into the container.
COPY --chown="${CONTAINER_APP_UID}:${CONTAINER_APP_GID}" image/scripts /srv/scripts

ENV PLUGINS_DIR="${CONTAINER_APP_ROOT}/app/plugins"
RUN git clone https://github.com/discourse/discourse-saml.git "${PLUGINS_DIR}/discourse-saml" \
# Remove additions incompatible with Discourse versions < 2.8
    && git -C "${PLUGINS_DIR}/discourse-saml" reset --hard 851f6cebe3fdd48019660b236a447abb6ddf9c89 \
    && mkdir -p "${PLUGINS_DIR}/discourse-saml/gems" \
# Have to determine the gems needed and install them now, otherwise Discourse will
# try to install them at runtime, which may not work due to network access issues.
    && echo 'source "https://rubygems.org"' > "${PLUGINS_DIR}/discourse-saml/Gemfile" \
    && grep -e ^gem "${PLUGINS_DIR}/discourse-saml/plugin.rb" >> "${PLUGINS_DIR}/discourse-saml/Gemfile" \
    && git clone https://github.com/discourse/discourse-solved.git "${PLUGINS_DIR}/discourse-solved" \
    && git clone https://github.com/canonical-web-and-design/discourse-markdown-note.git "${PLUGINS_DIR}/discourse-markdown-note" \
    && git clone https://github.com/unfoldingWord-dev/discourse-mermaid.git "${PLUGINS_DIR}/discourse-mermaid" \
    && chown -R "${CONTAINER_APP_USERNAME}:${CONTAINER_APP_GROUP}" "${PLUGINS_DIR}" \
# Have to determine the gems needed and install them now, otherwise Discourse will
# try to install them at runtime, which may not work due to network access issues.
    && su -s /bin/bash -c 'gem install bundler' "${CONTAINER_APP_USERNAME}" \
    && su -s /bin/bash -c '${CONTAINER_APP_ROOT}/app/bin/bundle install --gemfile=${PLUGINS_DIR}/discourse-saml/Gemfile --path=${PLUGINS_DIR}/discourse-saml/gems' "${CONTAINER_APP_USERNAME}" \
    && ln -s "${PLUGINS_DIR}/discourse-saml/gems/ruby/"* "${PLUGINS_DIR}/discourse-saml/gems/" \
    && su -s /bin/bash -c '${CONTAINER_APP_ROOT}/app/bin/bundle install' "${CONTAINER_APP_USERNAME}"
