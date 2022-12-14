To configure Discourse's SMTP you'll have to set the following configuration options with the appropriate values for your SMTP server by running `juju config [charm_name] [configuration]=[value]`:

```
smtp_address
smtp_authentication
smtp_domain
smtp_openssl_verify_mode
smtp_password
smtp_port
smtp_username
```

Note that not all of the configurations above might be needed dependending on the desired set up. For more details on the configuration options and their default values see the [configuration reference](https://charmhub.io/discourse-k8s/configure).
