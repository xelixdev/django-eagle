<p align="center">
  <img src="assets/eagle.svg" alt="django-eagle" width="480">
</p>

# django-eagle

[![CI](https://github.com/xelixdev/django-eagle/actions/workflows/ci.yml/badge.svg)](https://github.com/xelixdev/django-eagle/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/xelixdev/django-eagle/branch/main/graph/badge.svg)](https://codecov.io/gh/xelixdev/django-eagle)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-5.2%2B-092e20)](https://www.djangoproject.com/)

Catch wasted eager loads in your Django ORM queries.

When you `select_related(...)` or `prefetch_related(...)` a relation but never actually read it during a request, you've paid for a join or extra query for nothing. `django-eagle` watches relation access per request and warns you about eager loads that were never used.

## A minimal example

```python
# views.py
def eagle_detail(request, pk):
    # select_related("location") joins the location table...
    eagle = Eagle.objects.select_related("location").get(pk=pk)

    # ...but the response only reads eagle.name — location is never touched.
    return JsonResponse({"name": eagle.name})
```

That join was evaluated and thrown away. With `django-eagle` installed, the request emits:

```
UnusedRelatedAccess: select_related("location") was loaded but never accessed
on <Eagle instance>. Queryset marked at /app/views.py:3.
```

Drop the `select_related("location")` and the warning goes away — along with the wasted join.

## How it works

On app startup, eagle instruments your **first-party** models (apps that don't live under `site-packages`). For each request it:

1. Records every relation loaded via `select_related` / `prefetch_related`.
2. Records every relation that was actually accessed.
3. At the end of the request, emits an `UnusedRelatedAccess` warning for anything loaded but never accessed.

Third-party and stdlib app models are never instrumented, so you only get signal about code you own.

## Requirements

- Python >= 3.10
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

eagle is disabled by default. When disabled, eagle skips all instrumentation at app startup and the middleware becomes a no-op. To turn it on - set:

```python
EAGLE_ENABLED = True
```

To keep it on for local development/CI and off in production, I suggest:

```python
EAGLE_ENABLED = DEBUG
```

### Use

Run your app and send a request that hits one of your views. If that view eager-loads a relation it never reads, you'll see a warning:

```
UnusedRelatedAccess: select_related("location") was loaded but never accessed
on <Eagle instance>. Queryset marked at /app/views.py:42.
```

Fix it by dropping the unused `select_related` / `prefetch_related`, or tell eagle the access is legitimate (see below).

## Suppressing false positives

eagle spots access by intercepting Django's relation descriptors, which fire on ordinary attribute access — so template rendering, conditional reads, and Python-level serializers (including DRF) are all tracked while they run. A warning is still a false positive in the following cases:

- **The relation is only read on some code paths** — a queryset built up front (often a DRF `get_queryset`) can be returned early, on a (serializer) validation error or permission check, before anything reads the relation. You may also have conditional logic in a serializer which prevents your field from being read in certain cases. The eager load is right for the common path, but on that request the relation went untouched, so eagle flags it.

Reach for one of these escape hatches:

### `mark_considered` — mark relations as accessed imperatively

Call it with the model first (a class or its name string), followed by one or more relation cache names. Eagle then treats those relations as accessed for the rest of the current request:

```python
from eagle import mark_considered

mark_considered(Eagle, "location", "previous_locations")
```

**When you'd use this:** a DRF view eager-loads in `get_queryset`, but an action returns early — on a permission check, a (serializer) validation error, or other custom logic — before the serializer reads the relation. The load is right for the normal flow, so silence the warning on the early-return path instead of dropping the `select_related`:

```python
class EagleViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return Eagle.objects.select_related("location")

    def retrieve(self, request, *args, **kwargs):
        eagle = self.get_object()
        if not request.user.can_view(eagle):
            mark_considered(Eagle, "location")  # not read on this path, but the load is intentional
            return Response(status=403)
        return Response(self.get_serializer(eagle).data)  # reads location
```

The same applies to a serializer that reads a relation only inside a conditional branch: on requests where the branch doesn't run, mark it so the intentional load isn't flagged. `mark_considered` is a no-op when no request is being tracked, so it's safe to leave in code paths that also run outside a request (management commands, shell, tests).

**Use it sparingly.** Every `mark_considered` call is a standing assertion that a relation is used — it stays in the code and unconditionally forces eagle to treat the relation as accessed, even if a later refactor stops reading it. That turns off exactly the signal eagle exists to give you, so reach for it only when an eager load is genuinely justified but unobservable on a path, prefer the narrower [`may_access`](#may_access--decorator-that-marks-on-normal-return) or an [ignore rule](#eagle_warn_unused_ignore--ignore-rules-in-settings) where they fit, and audit existing calls periodically to make sure each is still earning its place.

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

eagle decides whether to instrument each installed app like this:

- **First-party apps** (those not under `site-packages`) are instrumented by default.
- **Third-party apps** are instrumented only when their module name matches an entry in `EAGLE_THIRD_PARTY_INCLUDE_APPS`.
- **`EAGLE_EXCLUDE_APPS` overrides both** — a listed app is never instrumented, even if it's first-party or explicitly included.

## Public API

Everything you need is exported from the top-level `eagle` package:

| Name | Type | Purpose |
| --- | --- | --- |
| `EagleWarnUnusedMiddleware` | middleware | Scopes tracking per request; emits warnings on response. |
| `mark_considered` | function | Imperatively mark relations as accessed. |
| `may_access` | decorator | Mark relations as accessed on normal return. |
| `UnusedRelatedAccess` | warning | Category emitted for an unused eager load. |

## Contributing

Contributions are welcome — please read [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up the project, run the tests, and propose changes. (In short: open an issue to agree on an approach first, and include tests with any code change.)

## License

`django-eagle` is released under the [MIT License](LICENSE).
