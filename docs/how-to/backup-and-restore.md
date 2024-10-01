# How to back up and restore Discourse

This document shows how to back up and restore Discourse.

There are two ways to backup and restore Discourse. The
first one is using the backup functionality provided by Discourse.

The second one consists in backing up and restoring the database directly,
that can be done easily thanks to [Charmed PostgreSQL](https://charmhub.io/postgresql)
and [Charmed PostgreSQL K8s](https://charmhub.io/postgresql-k8s).

For this How-to, it is supposed that S3 has been configured (see [how to configure S3](./configure-s3.md).
Running the Discourse Operator without S3 configured is not recommended as it will not work in HA mode and
it is risky and data loss can happen if the workload container is restarted.


## Backup and restore using Discourse backup functionality

It is recommended to configure the `s3_backup_bucket` to a bucket that will store the
backups (see [how to configure S3](./configure-s3.md)). If  `s3_backup_bucket` is not set,
the backups will be placed in one of the workload containers,
in the path `/srv/discourse/app/public/backups/`. This will make HA deployments work incorrectly.
Besides, it will be necessary to get the backup files and put them in a more secure place,
using Discourse admin interface or [juju scp](https://juju.is/docs/juju/juju-scp).

A backup can be made by a site administrator using the web interface. See
[Create, download, and restore a backup of your Discourse database](https://meta.discourse.org/t/create-download-and-restore-a-backup-of-your-discourse-database/122710/1)
for the full process.

Backups can also be configured to be automatically created. See [Configure automatic backups for Discourse](https://meta.discourse.org/t/configure-automatic-backups-for-discourse/14855/1) for the full process.


## Backup and restore using PostgreSQL

If the same S3 bucket can be used in the restored Discourse instance, then it is only necessary
to backup the database.

This can be easily done with [Charmed PostgreSQL](https://charmhub.io/postgresql) and [Charmed PostgreSQL K8s](https://charmhub.io/postgresql-k8s).
See [How to create and list backups in Charmed PostgreSQL](https://charmhub.io/postgresql/docs/h-create-and-list-backups)
or [How to create and list backups in Charmed PostgreSQL K8s](https://charmhub.io/postgresql-k8s/docs/h-create-and-list-backups) for the full procedure.

To restore Discourse, once it is deployed and configured as the Discourse instance to restore, it is only necessary
to restore the database. The instructions, depending on the configuration, can be found in the next links:
 - Charmed PostgreSQL. Local backup: https://charmhub.io/postgresql/docs/h-restore-backup
 - Charmed PostgreSQL. Migrate a cluster: https://charmhub.io/postgresql/docs/h-migrate-cluster-via-restore
 - Charmed PostgreSQL K8s. Local backup: https://charmhub.io/postgresql-k8s/docs/h-restore-backup
 - Charmed PostgreSQL K8s. Migrate a cluster: https://charmhub.io/postgresql-k8s/docs/h-migrate-cluster-via-restore

## S3 and the backup and restore procedure

If S3 is configured, the S3 bucket contains all the uploaded files. This information should also be backed up,
but it is not explained in this How-to.

If the S3 bucket used in the restored Discourse is not the same bucket as the original one, extra steps must be
done, see [moving from one S3 bucket to another](https://meta.discourse.org/t/moving-from-one-s3-bucket-to-another/184779)
for more information. You can run the remap command with: `juju ssh --container discourse discourse-k8s/0 pebble  exec --context=discourse --user=_daemon_ -w=/srv/discourse/app/ -- bundle exec /srv/discourse/app/script/discourse backup`
and rake tasks with a command like: `juju ssh --container discourse discourse-k8s/0 pebble exec --context=discourse --user=_daemon_ -w=/srv/discourse/app/ -- bundle exec rake posts:rebake`.