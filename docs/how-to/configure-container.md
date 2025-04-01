# How to configure the container

This charm exposes several configurations to tweak the behaviour of Discourse. These can by changes by running `juju config [charm_name] [configuration]=[value]`. Below you can find some of the options that will allow you to modify the charm's behaviour:

* CORS policies can be modified with the settings [cors_origin](https://charmhub.io/discourse-k8s/configure#cors_origin) and [enable_cors](https://charmhub.io/discourse-k8s/configure#enable_cors)
* The developer mails can be set through [developer_emails](https://charmhub.io/discourse-k8s/configure#developer_emails)
* Throttle level protections provided by Discourse can be changed via [throttle_level](https://charmhub.io/discourse-k8s/configure#throttle_level)

For a comprehensive list of configuration options check the [configuration reference](https://charmhub.io/discourse-k8s/configure).