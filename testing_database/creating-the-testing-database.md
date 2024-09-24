# Creating the testing database
At the writing this document, the testing database is created using Discourse v3.2.0 and used to test migration from v3.2.0 to v3.3.0.

## Creating the database
First of all we need to deploy the Discourse following the [tutorial](https://github.com/canonical/discourse-k8s-operator/blob/main/docs/tutorial.md).

Then, we need to create a 2 new users for testing using the actions:

`juju run discourse-k8s/0 create-user email=email@example.com admin=true`
`juju run discourse-k8s/0 create-user email=email2@example.com`

Please note that the first user is an admin and the second one is not. Also please not the passwords that are generated automatically by the command.

Now open the Discourse URL in a browser, login with the first user (admin) and create a new topic. Reply to this topic as the admin user again. Then, login with the second user and reply to this topic. Then login with the first user and approve the second users reply.

## Exporting the database

First we need to get the database password:
`juju run postgresql-k8s/0 get-password username=operator`

Ssh into the database
`juju ssh --container postgresql postgresql-k8s/0 bash`

Create a folder to dump the db
`mkdir -p /srv/dump/`

Dump the db. Ip here is the unit ip
`pg_dump -Fc -h 10.1.187.134 -U operator -d discourse > "/srv/dump/testing_database.sql"`

Exit the container
`exit`

Copy the dump into local file system.
`juju scp --container postgresql postgresql-k8s/0:/srv/dump/testing_database.sql./testing_database.sql`
