from collections.abc import Iterable

from django.db.models import Model

from eagle.logger import logger
from eagle.unused.state import LoadedRelation, collector


def _record_loaded(model_name: str, cache_name: str, kind: str, location: str | None) -> None:
    if not collector.active:
        return

    collector.loaded.setdefault(
        (model_name, cache_name),
        LoadedRelation(
            kind=kind,
            location=location,
        ),
    )


def _record_consumed(model_name: str, cache_name: str) -> None:
    if not collector.active:
        logger.debug("Tried recording consumed %s, %s... but collector is not active.", model_name, cache_name)
        return

    collector.consumed.add((model_name, cache_name))
    logger.debug("Recorded consumed %s, %s.", model_name, cache_name)


def mark_considered_internal(model_name: str, *cache_names: str) -> None:
    if not collector.active:
        return

    collector.consumed.update((model_name, cache_name) for cache_name in cache_names)


def init_state(instance: Model, location: str | None, locations: dict[str, str] | None = None) -> None:
    state = instance._state

    if getattr(state, "warn_unused", False):
        logger.debug("No warn_unused for %s, %s", instance.__class__.__name__, location)
        return

    state.warn_unused = True
    state.warn_unused_location = location
    state.warn_unused_locations = locations


def resolve_location(state: object, cache_name: str) -> str | None:
    locations = getattr(state, "warn_unused_locations", None)
    if locations is not None and cache_name in locations:
        return locations[cache_name]
    return getattr(state, "warn_unused_location", None)


def mark_select_related(instance: Model, cache_name: str) -> None:
    if not collector.active:
        logger.debug(
            "Tried marking select_related %s, %s... but collector is not active.",
            instance.__class__.__name__,
            cache_name,
        )
        return

    _record_loaded(
        model_name=instance.__class__.__name__,
        cache_name=cache_name,
        kind="select_related",
        location=resolve_location(instance._state, cache_name),
    )
    logger.debug("Marked select_related %s, %s.", instance.__class__.__name__, cache_name)


def mark_prefetched(instances: Iterable[Model], cache_name: str | None) -> None:
    if cache_name is None or not collector.active:
        logger.debug("Tried marking prefetch_related %s... but collector is not active.", cache_name or "")
        return

    for instance in instances:
        state = instance._state

        if not getattr(state, "warn_unused", False):
            logger.debug("No warn_unused for %s, %s.", instance.__class__.__name__, cache_name)
            continue

        _record_loaded(
            model_name=instance.__class__.__name__,
            cache_name=cache_name,
            kind="prefetch_related",
            location=resolve_location(state, cache_name),
        )
        logger.debug("Marked prefetch_related %s, %s.", instance.__class__.__name__, cache_name)


def mark_consumed(instance: Model, cache_name: str) -> None:
    if not collector.active:
        logger.debug("Tried marking consumed %s... but collector is not active.", cache_name)
        return

    _record_consumed(
        instance.__class__.__name__,
        cache_name,
    )
    logger.debug("Marked consumed %s, %s.", instance.__class__.__name__, cache_name)


mark_consumed_prefetched = mark_consumed
