# Contributing to django-eagle

**Before writing any code, please discuss your idea with the authors/maintainers first.** Open an issue describing the bug or feature so we can agree on the approach — this avoids wasted effort on changes that may not fit the project's direction. Once an approach is agreed, open a pull request and link it to that issue.

Any changes that you make must include unit tests.

## Getting set up

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone <repo-url>
cd django-eagle
uv sync
```

## Running the tests

Run the test suite (the env unsets guard against a sibling virtualenv leaking `DJANGO_SETTINGS_MODULE`):

```bash
env -u VIRTUAL_ENV -u DJANGO_SETTINGS_MODULE uv run --active pytest -q
```

Add `--cov` for a coverage report (config under `[tool.coverage.*]` in `pyproject.toml`):

```bash
env -u VIRTUAL_ENV -u DJANGO_SETTINGS_MODULE uv run --active pytest -q --cov
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs lint, type-check, and the test suite with coverage on every push and pull request, uploading coverage to Codecov.

Tests live under `tests/`, exercising a minimal Django app in `test_project/`. They run real requests/querysets and assert on captured warnings rather than internal state. Factories are in `tests/factories.py`; shared fixtures and base classes in `tests/conftest.py` and `tests/base.py`.

## Lint, format, and type-check

Lint and format with [ruff](https://docs.astral.sh/ruff/) (pinned in `.pre-commit-config.yaml`):

```bash
uvx ruff@0.15.12 check
uvx ruff@0.15.12 format
```

Type-check with [pyrefly](https://pyrefly.org/) (config lives under `[tool.pyrefly]` in `pyproject.toml`):

```bash
uv run pyrefly check
```

### Pre-commit hooks

All of the above run automatically via [pre-commit](https://pre-commit.com/) (or the faster Rust drop-in, [prek](https://github.com/j178/prek)). Install the hooks once so they run on every commit:

```bash
uvx pre-commit install        # or: prek install
```

Run every hook against the whole repo at any time:

```bash
uvx pre-commit run --all-files   # or: prek run --all-files
```

Conventions: absolute imports only, type hints on signatures, no comments/docstrings — let names and types carry the meaning.

## Adding a release note (contributors)

Releases are driven by [autopub](https://github.com/autopub/autopub). If your pull request should trigger a new release, add a `RELEASE.md` file at the repo root describing the change. The first line declares the [semver](https://semver.org/) bump; the rest becomes the changelog entry:

```markdown
Release type: patch

Fix false positive when a select_related relation is accessed only in a template.
```

`Release type` must be one of `major`, `minor`, or `patch`. Omit `RELEASE.md` entirely for changes that don't warrant a release (docs, CI, refactors).

## Releasing (maintainers)

Publishing is run manually from an up-to-date `main` with a `RELEASE.md` present (merged from a contributor's PR). autopub reads `RELEASE.md`, bumps the version in `pyproject.toml`, and prepends an entry to `CHANGELOG.md`.

Do it in one step:

```bash
uv run autopub deploy
```

`deploy` runs `prepare` → `build` → `commit` → `githubrelease` → `publish` in sequence. To go step by step (e.g. to inspect the version bump and changelog before pushing):

```bash
uv run autopub check          # confirm a RELEASE.md exists
uv run autopub prepare        # bump version + update CHANGELOG.md from RELEASE.md
uv run autopub build          # build the sdist/wheel into dist/
uv run autopub commit         # commit + push the version/changelog bump, remove RELEASE.md
uv run autopub githubrelease  # create the GitHub release (needs GITHUB_TOKEN)
uv run autopub publish        # upload to PyPI (needs PyPI credentials)
```

Credentials: `githubrelease` needs `GITHUB_TOKEN` in the environment; `publish` needs PyPI credentials (e.g. `TWINE_USERNAME`/`TWINE_PASSWORD` or a `~/.pypirc`). The committer identity used for the bump is configured under `[tool.autopub]` in `pyproject.toml`.
