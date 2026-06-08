# django-eagle

[![CI](https://github.com/xelixdev/django-eagle/actions/workflows/ci.yml/badge.svg)](https://github.com/xelixdev/django-eagle/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/xelixdev/django-eagle/branch/main/graph/badge.svg)](https://codecov.io/gh/xelixdev/django-eagle)
[![Python](https://img.shields.io/badge/python-3.13%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2%2B-092e20)](https://www.djangoproject.com/)

Catch wasted eager loads in your Django ORM queries.

When you `select_related(...)` or `prefetch_related(...)` a relation but never actually read it during a request, you've paid for a join or extra query for nothing. `django-eagle` watches relation access per request and warns you about eager loads that were never used.

## How it works

On app startup, eagle instruments your **first-party** models (apps that don't live under `site-packages`). For each request it:

1. Records every relation loaded via `select_related` / `prefetch_related`.
2. Records every relation that was actually accessed.
3. At the end of the request, emits an `UnusedRelatedAccess` warning for anything loaded but never accessed.

Third-party and stdlib app models are never instrumented, so you only get signal about code you own.

## Requirements

- Python >= 3.13
- Django >= 5.2

## Getting started

### Install

```bash
pip install django-eagle
```

### Configure

Add the app and middleware in your settings:

```python
INSTALLED_APPS = [
    # ...
    "eagle",
]

MIDDLEWARE = [
    # ...
    "eagle.middleware.EagleWarnUnusedMiddleware",
]
```

> **Ordering matters.** eagle works by swapping Django's related descriptors. If you use another library that also patches those descriptors — for example [django-seal](https://github.com/charettes/django-seal) — list `eagle` **below** it in `INSTALLED_APPS` so eagle wraps the already-patched descriptors rather than the other way around.

The middleware is what scopes tracking to a request and flushes warnings when the response is returned. Without it, no warnings fire.

### Enable / disable

eagle is enabled by default. To turn it off entirely — no ORM patching, no per-request tracking, zero runtime overhead — set:

```python
EAGLE_ENABLED = False
```

When disabled, eagle skips all instrumentation at app startup and the middleware becomes a no-op. Keep it on in development/CI and off in production, for example:

```python
EAGLE_ENABLED = DEBUG
```

### Use

Run your app and exercise a view. If a query eager-loads a relation that the view never reads, you'll see a warning:

```
UnusedRelatedAccess: select_related("location") was loaded but never accessed
on <Eagle instance>. Queryset marked at /app/views.py:42.
```

Fix it by dropping the unused `select_related` / `prefetch_related`, or tell eagle the access is legitimate (see below).

## Suppressing false positives

Some relations are accessed in ways eagle can't see (e.g. conditionally accessed, serialized in C, passed to a template, consumed by a library). Three escape hatches:

### `mark_considered` — mark relations as accessed imperatively

```python
from eagle import mark_considered

mark_considered(Eagle, "location", "previous_locations")
```

Accepts a model class or a model-name string, plus one or more relation cache names. No-op when no request is being tracked.

### `may_access` — decorator that marks on normal return

```python
from eagle import may_access

@may_access(Eagle, "location")
def serialize(eagle):
    ...
```

Marks the relations as accessed when the wrapped callable returns normally (works for sync and async functions). If it raises, nothing is marked. Wrapper metadata (`__name__`, `__doc__`) is preserved.

### `EAGLE_WARN_UNUSED_IGNORE` — ignore rules in settings

```python
EAGLE_WARN_UNUSED_IGNORE = [
    {"model": "Eagle", "field": "location"},   # specific model + field
    {"field": "created_by"},                   # any model, this field
    {"location": "*/legacy/*"},                # fnmatch glob on the call site
]
```

A rule matches when every key it specifies matches; an empty/partial rule matches broadly. `location` is matched as an `fnmatch` glob against the `file:line` where the queryset was built.

### `EAGLE_EXCLUDE_APPS` — opt whole apps out of instrumentation

```python
EAGLE_EXCLUDE_APPS = ["reporting", "legacy"]
```

App labels listed here are skipped entirely.

### `EAGLE_THIRD_PARTY_INCLUDE_APPS` — opt installed packages into instrumentation

By default eagle only instruments first-party apps (those that don't live under `site-packages`). If your models are shipped from an installed package — for example a shared models library — list the package here to force instrumentation. Entries are matched against each app's dotted module name (`AppConfig.name`), so naming a package opts in every app it contains:

```python
EAGLE_THIRD_PARTY_INCLUDE_APPS = ["my_shared_models"]
```

An app is instrumented when its label is **not** in `EAGLE_EXCLUDE_APPS` **and** (it is first-party **or** its module is under a package in `EAGLE_THIRD_PARTY_INCLUDE_APPS`). `EAGLE_EXCLUDE_APPS` (matched by app label) always wins.

## Public API

Everything you need is exported from the top-level `eagle` package:

| Name | Type | Purpose |
| --- | --- | --- |
| `EagleWarnUnusedMiddleware` | middleware | Scopes tracking per request; emits warnings on response. |
| `mark_considered` | function | Imperatively mark relations as accessed. |
| `may_access` | decorator | Mark relations as accessed on normal return. |
| `UnusedRelatedAccess` | warning | Category emitted for an unused eager load. |

## Contributing

**Before writing any code, please discuss your idea with the authors/maintainers first.** Open an issue describing the bug or feature so we can agree on the approach — this avoids wasted effort on changes that may not fit the project's direction. Once an approach is agreed, open a pull request and link it to that issue.

Any changes that you make must include unit tests.

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
git clone <repo-url>
cd django-eagle
uv sync
```

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

### Adding a release note (contributors)

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
