# AGENTS.md — discourse-k8s-operator

Quick reference for AI agents working in this repository.

## Repo overview

Juju charm that deploys [Discourse](https://www.discourse.org/) on Kubernetes.
The charm (`src/`) pairs with a custom OCI rock (`discourse_rock/`) built with
[Rockcraft](https://canonical-rockcraft.readthedocs-hosted.com/).

Key directories:

| Path | Contents |
|---|---|
| `src/` | Charm Python source (`charm.py`) |
| `discourse_rock/` | Rockcraft definition, patches, scripts for the OCI image |
| `tests/unit/` | Unit tests (pytest) |
| `tests/integration/` | Integration tests (pytest + jubilant + Juju) |
| `testing_database/` | Pre-seeded PostgreSQL dump for migration tests |
| `.agents/skills/` | Agent skill definitions and scripts |

## Environment

- **Juju + MicroK8s are available** — controller `concierge-microk8s`, default
  model `testing`. Integration tests can and must be run locally.
- **Host OS:** Ubuntu 24.04. Charm targets Ubuntu 22.04 (managed build via LXD).
- **`uv` may not be on PATH** — prefix commands with `PATH="$HOME/.local/bin:$PATH"`.
  Use `UV_PROJECT_ENVIRONMENT=/tmp/discourse-venv` to avoid broken `.venv` symlinks.

## Working directory discipline

**All temporary work goes in `/tmp`.** Never create working directories, clones,
or venvs inside the repo root.

```bash
# Good
WORKDIR=$(mktemp -d /tmp/my-task.XXXXXX)

# Bad — pollutes repo
mkdir discourse_clone   # inside repo root
```

## Running tests

See `CONTRIBUTING.md` for the full development setup. The project uses `uv` (no `tox.ini` — CONTRIBUTING.md's `tox -e` references are outdated):

```bash
# Unit tests
PATH="$HOME/.local/bin:$PATH" UV_PROJECT_ENVIRONMENT=/tmp/discourse-venv \
  uv run --group unit pytest tests/unit -v

# Integration tests — requires Juju + MicroK8s (see CONTRIBUTING.md §Deploy for setup)
PATH="$HOME/.local/bin:$PATH" UV_PROJECT_ENVIRONMENT=/tmp/discourse-venv \
  uv run --group integration pytest tests/integration/ -v \
    --model <model> --charm-file <charm.charm> \
    --discourse-image localhost:32000/discourse:<tag>
```

The rock is built and pushed per `CONTRIBUTING.md` §"Build the rock and charm":
```bash
cd discourse_rock && rockcraft pack
skopeo --insecure-policy copy --dest-tls-verify=false \
  oci-archive:<rock>.rock docker://localhost:32000/<app>:<tag>
```

## Shell scripts

All `.sh` files are linted with shellcheck in CI. Run before finishing any
task that touches shell scripts:

```bash
shellcheck -f gcc <script>.sh
```

## Git

- Commits require GPG signing — the environment may not have a GPG key. Signal
  the human when ready to commit rather than attempting to push yourself.
- `.gitignore` covers `.venv`, `.tmp`, `*.rock`, `*.charm`, `*.egg-info/`.
  Anything generated should land in one of those or `/tmp`.
