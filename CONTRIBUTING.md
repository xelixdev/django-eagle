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

```bash
uv run --active pytest -q
```

Add `--cov` for a coverage report (config under `[tool.coverage.*]` in `pyproject.toml`):

```bash
uv run --active pytest -q --cov
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs lint, type-check, and the test suite with coverage on every push and pull request. On pushes to `main`, the coverage badge (`assets/coverage.svg`) is regenerated with [genbadge](https://github.com/smarie/python-genbadge) and committed back to the repo.

All test assets live under `tests/`: the pytest suite sits at the root, the minimal Django app under test is in `tests/test_project/`, and `tests/excluded_app/` covers excluded-app behavior. Tests run real requests/querysets and assert on captured warnings rather than internal state. Factories are in `tests/factories.py`; shared fixtures and base classes in `tests/base.py`.

## Lint, format, and type-check

All checks (ruff lint/format, pyrefly type-check) run via [pre-commit](https://pre-commit.com/) (or the faster Rust drop-in, [prek](https://github.com/j178/prek)). Install the hooks once so they run on every commit:

```bash
uvx pre-commit install        # or: prek install
```

Run every hook against the whole repo at any time:

```bash
uvx pre-commit run --all-files   # or: prek run --all-files
```

Conventions: absolute imports only, type hints on signatures, no comments/docstrings — let names and types carry the meaning.
