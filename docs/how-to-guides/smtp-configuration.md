To configure Discourse's SMTP you'll have to set the following configuration options with the appropriate values for your SMTP server by running `juju config [charm_name] [configuration]=[value]`.

Set `smtp_address`to the SMTP server IP or hostname, `smtp_port` for the SMTP sever port if different from the default and `smtp_domain` to set the sender domain address.

If authentication is needed, `smtp_authentication` will need to be set to the appropriate authentication method. The credencials can be set with `smtp_username`and `smtp_password`.

If needed, the verification of the SSL certs can be turned on and off with `smtp_openssl_verify_mode`.

For more details on the configuration options and their default values see the [configuration reference](https://charmhub.io/discourse-k8s/configure).
