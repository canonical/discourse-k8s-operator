The application can be scaled to multiple pods simply by using [Juju’s `scale-application` command](https://juju.is/docs/scaling-applications#heading--scaling-up). Discourse will use the database to register and discover cluster members; no additional service or infrastructure is needed.

### Static content and uploads

Discourse supports post uploads. When using this charm you need to make use of the S3 storage option built in to discourse for file uploads.

To do this set the `s3_enabled` configuration option to `True` and specify the related configuration options for S3, such as `s3_bucket` and `s3_endpoint`.

If you deploy a discourse application without s3 enabled, and then subsequently enable s3 storage support, you need to run the following to migrate content to s3:

```
# From a discourse-k8s pod
export RAILS_ENV=${DISCOURSE_RAILS_ENVIRONMENT:-production}
cd ~discourse/app
su -s /bin/bash -c "rake uploads:migrate_to_s3 RAILS_ENV=$RAILS_ENV" discourse
```
The output will be as follows:
```
Please note that migrating to S3 is currently not reversible! 
[CTRL+c] to cancel, [ENTER] to continue

Migrating uploads to S3 for 'default'...
Uploading files to S3...
 - Listing local files
find: 'uploads/default/original': No such file or directory
 => 0 files
 - Listing S3 files
. => 2 files
 - Syncing files to S3

Updating the URLs in the database...
Removing old optimized images...
Flagging all posts containing lightboxes for rebake...
0 posts were flagged for a rebake
No posts require rebaking
Done!
```
This functionality will be provided as a juju action when https://bugs.launchpad.net/charm-k8s-discourse/+bug/1961025 is fixed.
