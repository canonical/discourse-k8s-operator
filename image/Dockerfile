# To be used for determining the image type to build.
ARG IMAGE_TYPE=base

FROM ubuntu:focal AS base-image

# ARGS become environment variables, but can be overridden using the
# --build-arg var=foo option to docker build. This allows you to have a
# default build image, but customize certain options such as app version or
# userids, etc.
ARG CONTAINER_APP_NAME
ARG CONTAINER_APP_VERSION
ARG CONTAINER_APP_USERNAME
ARG CONTAINER_APP_UID
ARG CONTAINER_APP_GROUP
ARG CONTAINER_APP_GID

# Used in Launchpad OCI Recipe build to tag the image.
LABEL org.label-schema.version=${CONTAINER_APP_VERSION:-v2.7.10}

# Copy any args we got into the environment.
ENV CONTAINER_APP_NAME ${CONTAINER_APP_NAME:-discourse}
ENV CONTAINER_APP_VERSION ${CONTAINER_APP_VERSION:-v2.7.10}
ENV CONTAINER_APP_USERNAME ${CONTAINER_APP_USERNAME:-discourse}
ENV CONTAINER_APP_UID ${CONTAINER_APP_UID:-200}
ENV CONTAINER_APP_GROUP ${CONTAINER_APP_GROUP:-discourse}
ENV CONTAINER_APP_GID ${CONTAINER_APP_GID:-200}

# CONTAINER_APP_ROOT is where files related to this application go. This
# environment variable is available in the build scripts. This should usually be
# a subdirectory of /srv.
ENV CONTAINER_APP_ROOT=/srv/discourse

# Application specific environment variables go here.
ENV GEM_HOME ${CONTAINER_APP_ROOT}/.gem

# We don't want packages prompting us during install.
ENV DEBIAN_FRONTEND=noninteractive

# Copy our build and runtime scripts into the image.
COPY --chown=${CONTAINER_APP_UID}:${CONTAINER_APP_GID} build_scripts /srv/build_scripts

# The setup_base_layer script performs steps that are very unlikely to change
# for this image.
RUN /srv/build_scripts/setup_base_layer

# The get_app_dependencies script gets any application-specific packages needed
# for this build.
RUN /srv/build_scripts/get_app_dependencies

# Run build process.
RUN /srv/build_scripts/build_app

# Run post-build cleanup.
RUN /srv/build_scripts/cleanup_post_build

# Copy run-time scripts into the container.
COPY --chown=${CONTAINER_APP_UID}:${CONTAINER_APP_GID} scripts /srv/scripts

# Set our entrypoint.
ENTRYPOINT /srv/scripts/pod_start

# Create different image types with different plugins. Call docker build with
# IMAGE_TYPE set to one of the image types below to create the appropriate
# image.

# 'base' image type adds no new plugins.
FROM base-image AS base
RUN echo "base image complete"

# 'markdown-saml' image type. This will use login.ubuntu.com as the SAML
# provider, and will disabled local logins over SAML logins using the
# `saml_full_screen_login` option.
FROM base-image AS markdown-saml

RUN cd ${CONTAINER_APP_ROOT}/app/plugins && git clone https://github.com/discourse/discourse-saml.git
# Remove additions incompatible with Discourse versions < 2.8
RUN cd ${CONTAINER_APP_ROOT}/app/plugins/discourse-saml && git reset --hard 851f6cebe3fdd48019660b236a447abb6ddf9c89
RUN cd ${CONTAINER_APP_ROOT}/app/plugins && git clone https://github.com/canonical-web-and-design/discourse-markdown-note.git
RUN chown -R ${CONTAINER_APP_USERNAME}:${CONTAINER_APP_GROUP} ${CONTAINER_APP_ROOT}/app/plugins
# Have to determine the gems needed and install them now, otherwise Discourse will
# try to install them at runtime, which may not work due to network access issues.
RUN cd ${CONTAINER_APP_ROOT}/app/plugins/discourse-saml && mkdir -p gems && chown ${CONTAINER_APP_USERNAME} gems && echo 'source "https://rubygems.org"' > Gemfile ; grep -e ^gem plugin.rb >> Gemfile && su -s /bin/bash -c 'gem install bundler' ${CONTAINER_APP_USERNAME} && su -s /bin/bash -c '${CONTAINER_APP_ROOT}/app/bin/bundle install --gemfile=Gemfile --path=${CONTAINER_APP_ROOT}/app/plugins/discourse-saml/gems' ${CONTAINER_APP_USERNAME} && cd gems && ln -s ruby/* ./
RUN cd ${CONTAINER_APP_ROOT}/app && su -s /bin/bash -c 'bin/bundle install' ${CONTAINER_APP_USERNAME}

RUN echo "markdown-saml image complete"

# 'markdown-saml-solved' image type.
FROM base-image AS markdown-saml-solved

RUN cd ${CONTAINER_APP_ROOT}/app/plugins && git clone https://github.com/discourse/discourse-saml.git
# Remove additions incompatible with Discourse versions < 2.8
RUN cd ${CONTAINER_APP_ROOT}/app/plugins/discourse-saml && git reset --hard 851f6cebe3fdd48019660b236a447abb6ddf9c89
RUN cd ${CONTAINER_APP_ROOT}/app/plugins && git clone https://github.com/discourse/discourse-solved.git
RUN cd ${CONTAINER_APP_ROOT}/app/plugins && git clone https://github.com/canonical-web-and-design/discourse-markdown-note.git
RUN chown -R ${CONTAINER_APP_USERNAME}:${CONTAINER_APP_GROUP} ${CONTAINER_APP_ROOT}/app/plugins
# Have to determine the gems needed and install them now, otherwise Discourse will
# try to install them at runtime, which may not work due to network access issues.
RUN cd ${CONTAINER_APP_ROOT}/app/plugins/discourse-saml && mkdir -p gems && chown ${CONTAINER_APP_USERNAME} gems && echo 'source "https://rubygems.org"' > Gemfile ; grep -e ^gem plugin.rb >> Gemfile && su -s /bin/bash -c 'gem install bundler' ${CONTAINER_APP_USERNAME} && su -s /bin/bash -c '${CONTAINER_APP_ROOT}/app/bin/bundle install --gemfile=Gemfile --path=${CONTAINER_APP_ROOT}/app/plugins/discourse-saml/gems' ${CONTAINER_APP_USERNAME} && cd gems && ln -s ruby/* ./
RUN cd ${CONTAINER_APP_ROOT}/app && su -s /bin/bash -c 'bin/bundle install' ${CONTAINER_APP_USERNAME}

RUN echo "markdown-saml-solved image complete"

FROM base-image AS markdown-mermaid-saml-solved

RUN git clone https://github.com/discourse/discourse-saml.git ${CONTAINER_APP_ROOT}/app/plugins/discourse-saml
# Remove additions incompatible with Discourse versions < 2.8
RUN cd ${CONTAINER_APP_ROOT}/app/plugins/discourse-saml && git reset --hard 851f6cebe3fdd48019660b236a447abb6ddf9c89
RUN git clone https://github.com/discourse/discourse-solved.git ${CONTAINER_APP_ROOT}/app/plugins/discourse-solved
RUN git clone https://github.com/canonical-web-and-design/discourse-markdown-note.git ${CONTAINER_APP_ROOT}/app/plugins/discourse-markdown-note
RUN git clone https://github.com/unfoldingWord-dev/discourse-mermaid.git ${CONTAINER_APP_ROOT}/app/plugins/discourse-mermaid
RUN chown -R ${CONTAINER_APP_USERNAME}:${CONTAINER_APP_GROUP} ${CONTAINER_APP_ROOT}/app/plugins
# Have to determine the gems needed and install them now, otherwise Discourse will
# try to install them at runtime, which may not work due to network access issues.
RUN cd ${CONTAINER_APP_ROOT}/app/plugins/discourse-saml && install -d -o ${CONTAINER_APP_USERNAME}  gems && echo 'source "https://rubygems.org"' > Gemfile ; grep -e ^gem plugin.rb >> Gemfile && su -s /bin/bash -c 'gem install bundler' ${CONTAINER_APP_USERNAME} && su -s /bin/bash -c '${CONTAINER_APP_ROOT}/app/bin/bundle install --gemfile=Gemfile --path=${CONTAINER_APP_ROOT}/app/plugins/discourse-saml/gems' ${CONTAINER_APP_USERNAME} && cd gems && ln -s ruby/* ./
RUN cd ${CONTAINER_APP_ROOT}/app && su -s /bin/bash -c 'bin/bundle install' ${CONTAINER_APP_USERNAME}

RUN echo "markdown-mermaid-saml-solved image complete"

# Build the final image based on the IMAGE_TYPE specified.
FROM ${IMAGE_TYPE} AS final
# Redeclare IMAGE_TYPE variable so it can be referenced inside this build
# stage per
# https://docs.docker.com/engine/reference/builder/#understand-how-arg-and-from-interact
ARG IMAGE_TYPE
RUN echo "Used ${IMAGE_TYPE} image type"
