This document explains the processes and practices recommended for contributing enhancements to the Discourse operator.

* Generally, before developing enhancements to this charm, you should consider [opening an issue](https://github.com/canonical/discourse-k8s-operator/issues) explaining your use case.
* If you would like to chat with us about your use-cases or proposed implementation, you can reach us at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev) or [Discourse](https://discourse.charmhub.io/).
* Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library will help you a lot when working on new features or bug fixes.
* All enhancements require review before being merged. Code review typically examines
  * code quality
  * test coverage
  * user experience for Juju administrators of this charm.
For more details, check our [contibuting guide](https://github.com/canonical/is-charms-contributing-guide/blob/main/CONTRIBUTING.md).

## Developing

For any problems with this charm, please [report bugs here](https://github.com/canonical/discourse-k8s-operator/issues).

The code for this charm can be downloaded as follows:

```
git clone https://github.com/canonical/discourse-k8s-operator
```

To run tests, run `tox` from within the charm code directory.

To build and deploy a local version of the charm, simply run:

```
charmcraft pack
# Ensure you're connected to a juju k8s model, assuming you're on amd64
juju deploy ./discourse-k8s_ubuntu-20.04-amd64.charm
```
## Canonical Contributor Agreement

Canonical welcomes contributions to the Discourse Operator. Please check out our [contributor agreement](https://ubuntu.com/legal/contributors) if you’re interested in contributing to the solution.