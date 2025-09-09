# Contributing

This document explains the processes and practices recommended for contributing enhancements to the Discourse charm.

## Overview

- Generally, before developing enhancements to this charm, you should consider [opening an issue
  ](https://github.com/canonical/discourse-k8s-operator/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach
  us at [Canonical Matrix public channel](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarizing yourself with the [Juju documentation](https://canonical-juju.readthedocs-hosted.com/en/3.6/user/howto/manage-charms/)
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Once your pull request is approved, we squash and merge your pull request branch onto
  the `main` branch. This creates a linear Git commit history.
- For further information on contributing, please refer to our
  [Contributing Guide](https://github.com/canonical/is-charms-contributing-guide).

## Code of conduct

When contributing, you must abide by the
[Ubuntu Code of Conduct](https://ubuntu.com/community/ethos/code-of-conduct).

## Releases and versions

This project uses [semantic versioning](https://semver.org/).

Please ensure that any new feature, fix, or significant change is documented by
adding an entry to the [CHANGELOG.md](https://charmhub.io/discourse-k8s/docs/changelog) file.

To learn more about changelog best practices, visit [Keep a Changelog](https://keepachangelog.com/).

## Submissions

If you want to address an issue or a bug in this project,
notify in advance the people involved to avoid confusion;
also, reference the issue or bug number when you submit the changes.

- [Fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-forks)
  our [GitHub repository](https://github.com/canonical/discourse-k8s-operator)
  and add the changes to your fork, properly structuring your commits,
  providing detailed commit messages and signing your commits.
- Make sure the updated project builds and runs without warnings or errors;
  this includes linting, documentation, code and tests.
- Submit the changes as a
  [pull request (PR)](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

Your changes will be reviewed in due time; if approved, they will be eventually merged.

### Describing pull requests

To be properly considered, reviewed and merged,
your pull request must provide the following details:

- **Title**: Summarize the change in a short, descriptive title.

- **Overview**: Describe the problem that your pull request solves.
  Mention any new features, bug fixes or refactoring.

- **Rationale**: Explain why the change is needed.

- **Juju Events Changes**: Describe any changes made to Juju events, or
  "None" if the pull request does not change any Juju events.

- **Module Changes**: Describe any changes made to the module, or "None"
  if your pull request does not change the module.

- **Library Changes**: Describe any changes made to the library,
  or "None" is the library is not affected.

- **Checklist**: Complete the following items:

  - The [charm style guide](https://juju.is/docs/sdk/styleguide) was applied
  - The [contributing guide](https://github.com/canonical/is-charms-contributing-guide) was applied
  - The changes are compliant with [ISD054 - Managing Charm Complexity](https://discourse.charmhub.io/t/specification-isd014-managing-charm-complexity/11619)
  - The documentation is updated
  - The PR is tagged with appropriate label (trivial, senior-review-required)
  - The changelog has been updated

### Signing commits

To improve contribution tracking,
we use the [Canonical contributor license agreement](https://assets.ubuntu.com/v1/ff2478d1-Canonical-HA-CLA-ANY-I_v1.2.pdf)
(CLA) as a legal sign-off, and we require all commits to have verified signatures.

#### Canonical contributor agreement

Canonical welcomes contributions to the Discourse charm. Please check out our
[contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing to the solution.

The CLA sign-off is simple line at the
end of the commit message certifying that you wrote it
or have the right to commit it as an open-source contribution.

#### Verified signatures on commits

All commits in a pull request must have cryptographic (verified) signatures.
To add signatures on your commits, follow the
[GitHub documentation](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).

## Develop

To make contributions to this charm, you'll need a working [Juju development setup](https://www.google.com/search?q=https://juju.is/docs/sdk/dev-setup).

First, clone the repository:

```bash
git clone https://github.com/canonical/discourse-k8s-operator.git
cd discourse-k8s-operator
```

### Local Development and Testing

Our development workflow is managed by make. This provides a consistent set of commands for building, testing, and deploying the charm.

To see all available commands, run:
```bash
make help
```

#### Building Artifacts

You can build the ROCK OCI image and the charm artifact separately or together.

- **Build everything:**  
  ```bash
  make build
  ```

- **Build only the ROCK:**  
  ```bash
  make build-rock
  ```

- **Build only the charm:**  
  ```bash
  make build-charm
  ```

#### Running Tox Environments

You can also run tox test environments individually.

- **Run common tests:**  
  ```bash
  make lint  
  make unit
  ```

- **Run any other tox environment:** You can run any environment from tox.ini by prefixing it with `tox-`.  
  ```bash
  make tox-fmt  
  make tox-static
  ```

#### Deploying the Charm

Before deploying for the first time, you need to set up your Juju model.

* **Set up the model (run once):**  
  ```bash
  make setup-juju-model
  ```

* **Deploy the latest local build:** This command will automatically build and publish the necessary artifacts before deploying.  
  ```bash
  make deploy
  ```

#### Running Integration Tests

The most involved workflow is running the integration tests, which build and deploy the charm to a live Juju model before running the test suite.

You can run the full suite with a single command:

```bash
make integration
```

You can also customize the run by providing variables. For example, to test a specific version and run only a single test function:

```bash
CHARM_VERSION="rev211-rc1" TOX_INTEGRATION_ARGS="-k test_active" make tox-integration
```

Let's break down what this command does:

- **CHARM_VERSION="rev211-rc1"**: By default, the charm version is automatically generated from the current Git state (git describe) to ensure every build is traceable and unique. This override gives you manual control to "tag" a build with a specific identifier, such as a release candidate version, for targeted testing.  
- **TOX_INTEGRATION_ARGS="-k test_active"**: This passes the argument -k test_active through tox directly to pytest. This tells pytest to only run tests whose names contain "test_active".  
- **make tox-integration**: This is the core command that orchestrates the entire process:  
  1. Builds the ROCK OCI image.  
  2. Builds the charm artifact with the specified CHARM_VERSION.  
  3. Pushes the ROCK image to the local registry.  
  4. Deploys the charm to your Juju model.  
  5. Finally, runs the integration test suite via tox, applying your custom TOX_INTEGRATION_ARGS.


#### Debugging Integration test code

You can also easily debug integration test code by specifying the appropriate `TOX_CMD_PREFIX` environment variable for your IDE debugging setup.

For example, given the following default VSCode `launch.json` configuration:

```json
{
    "name": "Python Debugger: Remote Attach",
    "type": "debugpy",
    "request": "attach",
    "connect": {
        "host": "localhost",
        "port": 5678
    },
    "pathMappings": [
        {
            "localRoot": "${workspaceFolder}",
            "remoteRoot": "."
        }
    ]
},
```

The following command will launch the integration tests, wait for the debugger to attach and then proceed with the test:

```bash
TOX_CMD_PREFIX="python -m debugpy --listen 5678 --wait-for-client -m" make tox-integration
```
