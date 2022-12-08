By default, Discourse will be set up to create users locally, in the PostgreSQL database configured for the application. For local testing it's usually easiest to create a custom admin user via the rails console than to configure an email server that can send you a confirmation email. To do this, simply get a shell on the discourse workload pod, and then run:
```
cd /srv/discourse/app && ./bin/bundle exec rake admin:create RAILS_ENV=production
```
You'll then be prompted to enter login information that you can later use to connect to Discourse.

For production deployments, SAML authentication can be used by adding the SAML plugin in the docker image you're using. See the section on [plugins and custom images]( /t/discourse-documentation-plugins-custom-images/3802) for more details.
