To configure an S3 bucket you'll have to set the following configuration options with the appropriate values for your existing bucket `juju config [charm_name] [configuration]=[value]`:

```
s3_access_key_id
s3_bucket
s3_enabled
s3_endpoint
s3_region
s3_secret_access_key
```

To enable S3 to perform backups, you'll need to specify also `s3_backup_bucket`.

It is also possible to configure the S3 bucket to act as a CDN, for that, set `s3_cdn_url`. If you which to modify the CORS set up, you can do so by changing `s3_install_cors_rule`.


For more details on the configuration options and their default values see the [configuration reference](https://charmhub.io/discourse-k8s/configure).
