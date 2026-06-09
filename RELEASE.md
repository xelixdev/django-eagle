Release type: major

First public release of django-eagle — catch wasted eager loads in your Django ORM.

- Detects `select_related` / `prefetch_related` relations that are loaded but never accessed during a request, emitting `UnusedRelatedAccess` warnings.
- Per-request tracking scoped by `EagleWarnUnusedMiddleware`, with warnings flushed on response.
- Instruments only first-party models — third-party and stdlib apps are left untouched.
- Warnings pinpoint the `file:line` call site where the queryset was built.
- `mark_considered(...)` to imperatively mark relations as legitimately accessed.
- `@may_access(...)` decorator marks relations as accessed on normal return (sync and async).
- `EAGLE_WARN_UNUSED_IGNORE` settings rules to suppress false positives by model, field, or call-site glob.
- `EAGLE_EXCLUDE_APPS` / `EAGLE_THIRD_PARTY_INCLUDE_APPS` to fine-tune which apps are instrumented.
- `EAGLE_ENABLED` toggle for zero runtime overhead when off (e.g. disable in production).
- Cooperates with other descriptor-patching libraries (e.g. django-seal) via `INSTALLED_APPS` ordering.
- Fully typed, comment-free codebase with a pytest suite that asserts on real requests and captured warnings.
