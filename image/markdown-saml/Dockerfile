FROM discourse:v2.5.2

# CONTAINER_APP_ROOT is where files related to this application go. This
# environment variable is available in the build scripts. This should usually be
# a subdirectory of /srv.
ENV CONTAINER_APP_ROOT=/srv/discourse

# Application specific environment variables go here.
ENV GEM_HOME ${CONTAINER_APP_ROOT}/.gem

# We don't want packages prompting us during install.
ENV DEBIAN_FRONTEND=noninteractive

RUN cd ${CONTAINER_APP_ROOT}/app/plugins && git clone https://github.com/discourse/discourse-saml.git
RUN cd ${CONTAINER_APP_ROOT}/app/plugins && git clone https://github.com/canonical-web-and-design/discourse-markdown-note.git
RUN chown -R ${CONTAINER_APP_USERNAME}:${CONTAINER_APP_GROUP} ${CONTAINER_APP_ROOT}/app/plugins
RUN cd ${CONTAINER_APP_ROOT}/app && su -s /bin/bash -c 'bin/bundle install' ${CONTAINER_APP_USERNAME} 

RUN echo "saml_target_url = https://login.ubuntu.com/+saml" >> /srv/scripts/assets/discourse.conf.tmpl
RUN echo "saml_cert_fingerprint = 32:15:20:9F:A4:3C:8E:3E:8E:47:72:62:9A:86:8D:0E:E6:CF:45:D5" >> /srv/scripts/assets/discourse.conf.tmpl
RUN echo "saml_full_screen_login = true" >> /srv/scripts/assets/discourse.conf.tmpl
