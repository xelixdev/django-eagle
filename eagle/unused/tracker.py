import warnings

from eagle.exceptions import UnusedRelatedAccess
from eagle.logger import logger
from eagle.unused.ignore import should_ignore
from eagle.unused.state import LoadedRelation, collector


def is_active() -> bool:
    """
    Return True if Eagle is currently tracking a request.

    Returns:
        True when the request collector is active, False otherwise.
    """
    return collector.active


def begin_request() -> None:
    """Activate the collector for a new request."""
    logger.debug("Begin request.")
    collector.start()


def end_request() -> None:
    """Emit warnings for all loaded-but-not-consumed relations, then deactivate the collector."""
    logger.debug("End request.")

    if not collector.active:
        return

    for key, relation in sorted(collector.loaded.items()):
        if key in collector.consumed:
            continue

        model_label, cache_name = key
        # Keys carry the full label (app_label.ModelName); ignore rules and warning messages
        # speak in the bare class name, which is the segment after the final dot.
        model_name = model_label.rsplit(".", 1)[-1]

        if should_ignore(
            model_name,
            cache_name,
            relation.location,
        ):
            logger.debug("Ignoring %s, %s, %s", model_label, cache_name, relation.location)
            continue

        logger.debug("Found unused %s, %s, %s", model_label, cache_name, relation.location)
        _emit_unused_warning(
            model_name=model_name,
            cache_name=cache_name,
            relation=relation,
        )

    collector.stop()


def _emit_unused_warning(*, model_name: str, cache_name: str, relation: LoadedRelation) -> None:
    """
    Emit a single UnusedRelatedAccess warning with a descriptive message.

    Args:
        model_name: Django model class name where the relation was loaded.
        cache_name: ORM cache key for the relation.
        relation: Snapshot of the loaded relation including kind and call-site location.
    """
    location_suffix = f" Queryset marked at {relation.location}." if relation.location else ""

    warnings.warn(
        f'{relation.kind}("{cache_name}") was loaded but never accessed on <{model_name} instance>.{location_suffix}',
        category=UnusedRelatedAccess,
        stacklevel=2,
    )
