import warnings

from eagle.exceptions import UnusedRelatedAccess
from eagle.logger import logger
from eagle.unused.ignore import should_ignore
from eagle.unused.state import LoadedRelation, collector


def is_active() -> bool:
    return collector.active


def begin_request() -> None:
    logger.debug("Begin request.")
    collector.start()


def end_request() -> None:
    logger.debug("End request.")

    if not collector.active:
        return

    for (model_name, cache_name), relation in sorted(collector.loaded.items()):
        key = (model_name, cache_name)

        if key in collector.consumed:
            continue

        if should_ignore(
            model_name,
            cache_name,
            relation.location,
        ):
            logger.debug("Ignoring %s, %s, %s", model_name, cache_name, relation.location)
            continue

        logger.debug("Found unused %s, %s, %s", model_name, cache_name, relation.location)
        _emit_unused_warning(
            model_name=model_name,
            cache_name=cache_name,
            relation=relation,
        )

    collector.stop()


def _emit_unused_warning(*, model_name: str, cache_name: str, relation: LoadedRelation) -> None:
    location_suffix = f" Queryset marked at {relation.location}." if relation.location else ""

    warnings.warn(
        f'{relation.kind}("{cache_name}") was loaded but never accessed on <{model_name} instance>.{location_suffix}',
        category=UnusedRelatedAccess,
        stacklevel=2,
    )
