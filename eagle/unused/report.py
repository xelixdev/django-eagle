import contextvars
from collections.abc import Iterable
from dataclasses import dataclass

from django.apps import apps

from eagle.unused.ignore import should_ignore
from eagle.unused.state import collector


@dataclass(frozen=True)
class UnusedRelation:
    """A single eager-loaded relation that was never accessed during the request."""

    # ``app_label.ModelName`` -- the first segment of the collector key.
    model_label: str
    # Bare ``ModelName``, as used in warning messages and ignore rules.
    model_name: str
    # ORM cache key for the relation -- the second segment of the collector key.
    cache_name: str
    # ``"select_related"`` or ``"prefetch_related"``.
    kind: str
    # ``"file:line"`` where the queryset was built, or None when it could not be captured.
    location: str | None
    # How many instances carried this load (the fan-out).
    instances: int
    # Extra columns per row for select_related; None for prefetch_related or when unresolved.
    columns: int | None
    # Whether ``EAGLE_WARN_UNUSED_IGNORE`` suppresses the warning for this relation. The warning
    # path skips these; the Debug Toolbar panel still shows them (flagged) so they stay visible.
    warn_ignored: bool = False


# Holds the most recent request's full unused report (every loaded-but-unread relation, including
# warning-suppressed ones). Written by ``end_request`` before ``collector.stop()`` so a Debug
# Toolbar panel reading after the middleware has finished still sees the result, regardless of
# middleware ordering relative to the toolbar.
_last_report: contextvars.ContextVar[list[UnusedRelation]] = contextvars.ContextVar("eagle_last_report")


# Model labels (``app_label.ModelName``) instrumented only so the Debug Toolbar can profile them;
# their unused loads must never warn. Populated at startup by the app config when
# ``EAGLE_DEBUG_TOOLBAR_INCLUDE_EXCLUDED_APPS`` is on, and empty otherwise.
_warn_suppressed_labels: set[str] = set()


def register_warn_suppressed_labels(labels: Iterable[str]) -> None:
    """
    Record model labels whose unused loads must never warn (only surface in the panel).

    Args:
        labels: ``app_label.ModelName`` strings for the excluded-app models being profiled.
    """
    _warn_suppressed_labels.update(labels)


def clear_warn_suppressed_labels() -> None:
    """Forget all warn-suppressed labels; used in tests to reset between runs."""
    _warn_suppressed_labels.clear()


def _related_column_count(model_label: str, cache_name: str) -> int | None:
    """
    Best-effort count of concrete columns on the model a forward relation points to.

    Resolves *cache_name* back to a field on the model named by *model_label* and returns
    ``len(related_model._meta.concrete_fields)`` -- the extra per-row columns a select_related
    join materialises.

    Args:
        model_label: Django model label (``app_label.ModelName``) owning the relation.
        cache_name: ORM cache key identifying the forward relation field.

    Returns:
        The related model's concrete-field count, or None when *cache_name* maps to no relation
        field carrying a related model (generic FKs, renamed caches, lookups that no longer
        resolve) so the panel omits the estimate rather than guessing.
    """
    try:
        model = apps.get_model(model_label)
        for field in model._meta.get_fields():
            if getattr(field, "cache_name", None) == cache_name and getattr(field, "related_model", None):
                return len(field.related_model._meta.concrete_fields)
    except (LookupError, AttributeError):
        return None
    return None


def collect_all_unused() -> list[UnusedRelation]:
    """
    Return every relation loaded but never consumed in the current request, with no filtering.

    Each record is tagged with ``warn_ignored`` (whether ``EAGLE_WARN_UNUSED_IGNORE`` suppresses
    its warning), so the warning path and the Debug Toolbar panel can filter the same data
    differently. Reads the live collector without mutating it, so it is safe to call before
    ``end_request``. When no request is being tracked the collector is empty, so the result is
    an empty list.

    Returns:
        One ``UnusedRelation`` per loaded-but-unread relation, ordered deterministically by
        ``(model_label, cache_name)`` to match warning emission order.
    """
    report: list[UnusedRelation] = []

    for key, relation in sorted(collector.loaded.items()):
        if key in collector.consumed:
            continue

        model_label, cache_name = key
        # Keys carry the full label (app_label.ModelName); ignore rules and warning messages
        # speak in the bare class name, which is the segment after the final dot.
        model_name = model_label.rsplit(".", 1)[-1]

        # Columns are only meaningful for the per-row join of a select_related.
        columns = _related_column_count(model_label, cache_name) if relation.kind == "select_related" else None

        report.append(
            UnusedRelation(
                model_label=model_label,
                model_name=model_name,
                cache_name=cache_name,
                kind=relation.kind,
                location=relation.location,
                instances=collector.loaded_counts.get(key, 0),
                columns=columns,
                warn_ignored=(
                    model_label in _warn_suppressed_labels or should_ignore(model_name, cache_name, relation.location)
                ),
            )
        )

    return report


def collect_unused() -> list[UnusedRelation]:
    """
    Return the relations that should warn: loaded but never consumed, ignore rules applied.

    This is the warning view of :func:`collect_all_unused` -- the same set minus the relations
    suppressed by ``EAGLE_WARN_UNUSED_IGNORE``.

    Returns:
        One ``UnusedRelation`` per surviving relation, ordered deterministically by
        ``(model_label, cache_name)`` to match warning emission order.
    """
    return [relation for relation in collect_all_unused() if not relation.warn_ignored]


def set_last_report(report: list[UnusedRelation]) -> None:
    """
    Stash *report* as the most recent request's result so a panel can read it post-response.

    Args:
        report: The full list of unused relations produced by the request that just ended.
    """
    _last_report.set(report)


def get_last_report() -> list[UnusedRelation]:
    """
    Return the most recently stashed unused report for this context, or an empty list.

    The stash holds the full report (every loaded-but-unread relation, including the
    warning-suppressed ones), so a panel can apply its own filtering independently of warnings.

    Returns:
        The list set by the last ``end_request`` in this context, or ``[]`` if none.
    """
    return _last_report.get([])
