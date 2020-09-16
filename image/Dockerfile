FROM ubuntu:focal

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

# Copy any args we got into the environment.
ENV CONTAINER_APP_NAME ${CONTAINER_APP_NAME:-discourse}
ENV CONTAINER_APP_VERSION ${CONTAINER_APP_VERSION:-v2.4.3}
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
