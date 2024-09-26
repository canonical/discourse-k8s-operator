# How to contribute

## Overview

This document explains the processes and practices recommended for contributing
enhancements to the Discourse operator.

- Generally, before developing enhancements to this charm, you should consider
[opening an issue](https://github.com/canonical/discourse-k8s-operator/issues)
explaining your use case.
- If you would like to chat with us about your use-cases or proposed
implementation, you can reach us at [Canonical Matrix public channel](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk)
library will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically
examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Please help us out in ensuring easy to review branches by rebasing your pull
request branch onto the `main` branch. This also avoids merge commits and
creates a linear Git commit history.
- Please generate src documentation for every commit. See the section below for
more details.

## Developing

The code for this charm can be downloaded as follows:

```
git clone https://github.com/canonical/discourse-k8s-operator
```

You can use the environments created by `tox` for development:

```shell
tox --notest -e unit
source .tox/unit/bin/activate
```

### Testing

Note that the [Discourse](discourse_rock/rockcraft.yaml) image need to be built and 
pushed to microk8s for the tests to run. It should
be tagged as `localhost:32000/discourse:latest` so that Kubernetes knows how to pull them
from the MicroK8s repository. Note that the MicroK8s registry needs to be
enabled using `microk8s enable registry`. More details regarding the OCI image
below. The following commands can then be used to run the tests:

* `tox`: Runs all of the basic checks (`lint`, `unit`, `static`, and `coverage-report`).
* `tox -e fmt`: Runs formatting using `black` and `isort`.
* `tox -e lint`: Runs a range of static code analysis to check the code.
* `tox -e static`: Runs other checks such as `bandit` for security issues.
* `tox -e unit`: Runs the unit tests.
* `tox -e integration`: Runs the integration tests.

### Generating src docs for every commit

Run the following command:

```bash
echo -e "tox -e src-docs\ngit add src-docs\n" >> .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Build charm

Build the charm in this git repository using:

```shell
charmcraft pack
```
For the integration tests (and also to deploy the charm locally), the discourse 
image is required in the microk8s registry. To enable it:

```shell
    microk8s enable registry
```

The following commands import the images in the Docker daemon and push them into
the registry:

```shell
    cd [project_dir]/discourse_rock && rockcraft pack rockcraft.yaml
    rockcraft.skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:discourse_1.0_amd64.rock docker://localhost:32000/discourse:latest
```

### Deploy

```bash
# Create a model
juju add-model discourse-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
# Deploy the charm (assuming you're on amd64)
juju deploy ./discourse-k8s_ubuntu-20.04-amd64.charm \
  --resource discourse-image=localhost:32000/discourse:latest \
```

## Canonical Contributor Agreement

Canonical welcomes contributions to the Discourse Operator. Please check out our [contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing to the solution.