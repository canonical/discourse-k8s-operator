# Contributing

This document explains the processes and practices recommended for contributing enhancements to the Discourse charm.

## Overview

- Generally, before developing enhancements to this charm, you should consider [opening an issue
  ](https://github.com/canonical/discourse-k8s-operator/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach
  us at [Canonical Matrix public channel](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarizing yourself with the [Juju documentation](https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/)
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

## Changelog

Please ensure that any new feature, fix, or significant change is documented by
adding an entry to the [CHANGELOG.md](./docs/changelog.md) file. Use the date of the
contribution as the header for new entries.

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

  - The [charm style guide](https://documentation.ubuntu.com/juju/3.6/reference/charm/charm-development-best-practices/) was applied
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

To make contributions to this charm, you'll need a working
[development setup](https://documentation.ubuntu.com/juju/latest/user/howto/manage-your-deployment/manage-your-deployment-environment/).

The code for this charm can be downloaded as follows:

```
git clone https://github.com/canonical/discourse-k8s-operator
```

Make sure to install [`uv`](https://docs.astral.sh/uv/). For example, you can install `uv` on Ubuntu using:

```bash
sudo snap install astral-uv --classic
```

For other systems, follow the [`uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/).

Then install `tox` with its extensions, and install a range of Python versions:

```bash
uv python install
uv tool install tox --with tox-uv
uv tool update-shell
```

To create a development environment, run:

```bash
uv sync --all-groups
source .venv/bin/activate
```

### Test

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

* ``tox``: Executes all of the basic checks and tests (``lint``, ``unit``, ``static``, and ``coverage-report``).
* ``tox -e fmt``: Runs formatting using ``ruff``.
* ``tox -e lint``: Runs a range of static code analysis to check the code.
* ``tox -e static``: Runs other checks such as ``bandit`` for security issues.
* ``tox -e unit``: Runs the unit tests.
* ``tox -e integration``: Runs the integration tests.

### Running workflows locally

Most workflows can be run locally by registering a
[Multipass](https://multipass.run/) VM as a temporary GitHub self-hosted runner.
The workflow executes exactly as it does in real CI — dependencies like MicroK8s
and Juju are installed by the workflow itself.

> **Note:** The docs workflow (`docs.yaml`) cannot be run this way. The upstream
> reusable workflow hardcodes `runs-on: ubuntu-latest`, which always routes to
> GitHub-hosted runners. Docs checks run automatically on every push and pull
> request, so there is no need to run them locally.
>
> **Note:** Unit tests (`tox -e lint`, `tox -e unit`, `tox -e static`) have no
> infrastructure dependencies and are faster to run directly on your host machine
> as described in the [Test](#test) section above.

#### 1. Create the Multipass VM

```bash
multipass launch 24.04 \
  --name ci-runner \
  --cpus 4 \
  --memory 16G \
  --disk 60G
```

Then install packages that GitHub-hosted runners provide but a minimal Ubuntu
image omits:

```bash
multipass exec ci-runner -- sudo apt-get install -y \
  python3-pip python3-venv \
  make unzip shellcheck
```

#### 2. Register the VM as a self-hosted runner

```bash
# Get a one-time registration token
RUNNER_TOKEN=$(gh api \
  repos/canonical/discourse-k8s-operator/actions/runners/registration-token \
  --method POST --jq .token)

multipass exec ci-runner -- bash -c "
  mkdir -p ~/actions-runner && cd ~/actions-runner
  ARCH=\$(uname -m | sed 's/x86_64/x64/;s/aarch64/arm64/')
  RUNNER_VERSION=\$(curl -s https://api.github.com/repos/actions/runner/releases/latest \
    | grep tag_name | cut -d'\"' -f4 | sed 's/v//')
  curl -sL https://github.com/actions/runner/releases/download/v\${RUNNER_VERSION}/actions-runner-linux-\${ARCH}-\${RUNNER_VERSION}.tar.gz \
    | tar xz
  ./config.sh \
    --url https://github.com/canonical/discourse-k8s-operator \
    --token $RUNNER_TOKEN \
    --name ci-runner-local \
    --labels self-hosted,\${ARCH},local-multipass,noble \
    --replace \
    --unattended
"
```

#### 3. Temporarily change the runner label

The workflow routes jobs using all of `[self-hosted, <arch>, <label>, noble]` — every
label must match your runner. Change `self-hosted-runner-label` in the workflow you
want to run. For example, in `.github/workflows/integration_test.yaml`:

```diff
-      self-hosted-runner-label: "edge"
+      self-hosted-runner-label: "local-multipass"
```

#### 4. Start the runner

Install the runner as a systemd service so it starts automatically when the VM
boots and survives shell disconnections:

```bash
multipass exec ci-runner -- bash -c \
  'cd ~/actions-runner && sudo ./svc.sh install ubuntu && sudo ./svc.sh start'
```

If you prefer to run it manually (or the service is not installed), start it in
the background:

```bash
multipass exec ci-runner -- bash -c \
  'cd ~/actions-runner && nohup ./run.sh &>> ~/runner.log &'
```

Verify the runner is connected before triggering a workflow:

```bash
multipass exec ci-runner -- tail -5 ~/runner.log
# Should show: Listening for Jobs
```

#### Trigger the workflow

If the workflow triggers on `workflow_dispatch`. Trigger it via the github cli with:

```bash
gh workflow run WORKFLOW_FILE_NAME --ref YOUR_TARGET_BRANCH -f self-hosted-runner-label=local-multipass
```

If workflow triggers on `pull_request`. Open a draft PR on your branch to kick
it off:

```bash
gh pr create --draft --title "WIP: testing locally" --body ""
# Or if a PR is already open, a plain push is enough:
git push
```

Watch progress at `https://github.com/canonical/discourse-k8s-operator/actions`.

#### 5. Clean up when done

```bash
# Remove the runner registration
REMOVE_TOKEN=$(gh api \
  repos/canonical/discourse-k8s-operator/actions/runners/registration-token \
  --method POST --jq .token)
multipass exec ci-runner -- bash -c \
  "cd ~/actions-runner && ./config.sh remove --token $REMOVE_TOKEN"

# Revert the label change
git checkout .github/workflows/integration_test.yaml
```

### Build the rock and charm

Use [Rockcraft](https://documentation.ubuntu.com/rockcraft/stable/) to create an
OCI image for the Discourse app, and then upload the image to a MicroK8s registry,
which stores OCI archives so they can be downloaded and deployed.

Enable the MicroK8s registry:

```bash
microk8s enable registry
```

The following commands pack the OCI image and push it into
the MicroK8s registry:

```bash
cd <project_dir>/discourse_rock
rockcraft pack
skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:<rock-name>.rock docker://localhost:32000/<app-name>:latest
```

Build the charm in this git repository using:

```shell
charmcraft pack
```

### Deploy

```bash
# Create a model
juju add-model charm-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
# Deploy the charm
juju deploy ./discourse-k8s*.charm
```
