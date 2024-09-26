# How to configure S3

An S3 bucket can be leveraged to serve the static resources packaged by Discourse, potentically improving performance. Moreover, it is required when scaling the charm to serve the uploaded files. To configure it to set the following configuration options with the appropriate values for your existing bucket `juju config [charm_name] [configuration]=[value]`:

```
s3_access_key_id
s3_bucket
s3_enabled
s3_endpoint
s3_region
s3_secret_access_key
```

To enable S3 to perform backups, you'll need to specify also `s3_backup_bucket`.

It is also possible to configure the S3 bucket to act as a content delivery network (CDN) serving the static content directly from the bucket; for that, set `s3_cdn_url`. If you wish to modify the CORS set up, you can do so by changing `s3_install_cors_rule`.


For more details on the configuration options and their default values see the [configuration reference](https://charmhub.io/discourse-k8s/configure).