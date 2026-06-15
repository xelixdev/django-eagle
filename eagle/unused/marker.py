from collections.abc import Iterable

from django.db.models import Model

from eagle.logger import logger
from eagle.unused.state import LoadedRelation, collector


def _record_loaded(model_label: str, cache_name: str, kind: str, location: str | None) -> None:
    """
    Register a relation as loaded; first write wins so repeated loads don't overwrite the original location.

    Args:
        model_label: Django model label (``app_label.ModelName``).
        cache_name: ORM cache key for the relation (e.g. ``_author_cache``).
        kind: Relation type string, either ``"select_related"`` or ``"prefetch_related"``.
        location: Call-site string (``"file:line"``) captured when the queryset was built, or None.
    """
    if not collector.active:
        return

    collector.loaded.setdefault(
        (model_label, cache_name),
        LoadedRelation(
            kind=kind,
            location=location,
        ),
    )


def _record_consumed(model_label: str, cache_name: str) -> None:
    """
    Mark a relation key as consumed so it will not trigger an unused warning.

    Args:
        model_label: Django model label (``app_label.ModelName``).
        cache_name: ORM cache key for the relation.
    """
    if not collector.active:
        logger.debug("Tried recording consumed %s, %s... but collector is not active.", model_label, cache_name)
        return

    collector.consumed.add((model_label, cache_name))
    logger.debug("Recorded consumed %s, %s.", model_label, cache_name)


def mark_considered_internal(model_label: str, *cache_names: str) -> None:
    """
    Suppress warnings for *cache_names* on *model_label* without going through the public API.

    Args:
        model_label: Django model label (``app_label.ModelName``).
    """
    if not collector.active:
        return

    collector.consumed.update((model_label, cache_name) for cache_name in cache_names)


def init_state(instance: Model, location: str | None, locations: dict[str, str] | None = None) -> None:
    """
    Attach Eagle tracking flags to *instance._state*; no-op if already initialised.

    Args:
        instance: The Django model instance being yielded from a queryset.
        location: Queryset-level call-site string (``"file:line"``), or None.
        locations: Per-field call-site map keyed by cache_name, or None.
    """
    state = instance._state

    if getattr(state, "warn_unused", False):
        logger.debug("No warn_unused for %s, %s", instance.__class__.__name__, location)
        return

    state.warn_unused = True
    state.warn_unused_location = location
    state.warn_unused_locations = locations


def resolve_location(state: object, cache_name: str) -> str | None:
    """
    Return the most specific location for *cache_name*, falling back to the queryset-level location.

    Args:
        state: A Django model instance's ``_state`` object carrying Eagle tracking attributes.
        cache_name: ORM cache key for the relation.

    Returns:
        The per-field location string if available, otherwise the queryset-level string, or None.
    """
    locations = getattr(state, "warn_unused_locations", None)
    if locations is not None and cache_name in locations:
        return locations[cache_name]
    return getattr(state, "warn_unused_location", None)


def mark_select_related(instance: Model, cache_name: str) -> None:
    """
    Record a select_related field as loaded on *instance*.

    Args:
        instance: The model instance that owns the loaded relation.
        cache_name: ORM cache key for the select_related field.
    """
    if not collector.active:
        logger.debug(
            "Tried marking select_related %s, %s... but collector is not active.",
            instance.__class__.__name__,
            cache_name,
        )
        return

    _record_loaded(
        model_label=instance._meta.label,
        cache_name=cache_name,
        kind="select_related",
        location=resolve_location(instance._state, cache_name),
    )
    logger.debug("Marked select_related %s, %s.", instance.__class__.__name__, cache_name)


def mark_prefetched(instances: Iterable[Model], cache_name: str | None) -> None:
    """
    Record a prefetch_related field as loaded across *instances*.

    Args:
        instances: Iterable of model instances for which the prefetch was executed.
        cache_name: ORM cache key for the prefetched relation, or None to skip recording.
    """
    if cache_name is None or not collector.active:
        logger.debug("Tried marking prefetch_related %s... but collector is not active.", cache_name or "")
        return

    for instance in instances:
        state = instance._state

        if not getattr(state, "warn_unused", False):
            logger.debug("No warn_unused for %s, %s.", instance.__class__.__name__, cache_name)
            continue

        _record_loaded(
            model_label=instance._meta.label,
            cache_name=cache_name,
            kind="prefetch_related",
            location=resolve_location(state, cache_name),
        )
        logger.debug("Marked prefetch_related %s, %s.", instance.__class__.__name__, cache_name)


def mark_consumed(instance: Model, cache_name: str) -> None:
    """
    Record that a loaded relation was accessed on *instance*.

    Args:
        instance: The model instance whose relation was accessed.
        cache_name: ORM cache key for the accessed relation.
    """
    if not collector.active:
        logger.debug("Tried marking consumed %s... but collector is not active.", cache_name)
        return

    _record_consumed(
        instance._meta.label,
        cache_name,
    )
    logger.debug("Marked consumed %s, %s.", instance.__class__.__name__, cache_name)


mark_consumed_prefetched = mark_consumed
