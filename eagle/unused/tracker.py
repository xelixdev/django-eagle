import warnings

from eagle.exceptions import UnusedRelatedAccess
from eagle.logger import logger
from eagle.unused.report import UnusedRelation, collect_all_unused, set_last_report
from eagle.unused.state import collector


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
    """Emit warnings for all loaded-but-not-consumed relations, stash the report, then deactivate the collector."""
    logger.debug("End request.")

    if not collector.active:
        return

    report = collect_all_unused()
    for relation in report:
        # Warning-suppressed relations stay in the stashed report (so the panel can show them)
        # but never warn -- this is what keeps ``EAGLE_WARN_UNUSED_IGNORE`` behaviour intact.
        if relation.warn_ignored:
            continue
        logger.debug("Found unused %s, %s, %s", relation.model_label, relation.cache_name, relation.location)
        _emit_unused_warning(relation)

    # Stash the full report before stopping: ``collector.stop()`` installs a fresh empty state,
    # so a panel reading after the middleware has finished relies on this snapshot rather than
    # the live collector (which is empty by then).
    set_last_report(report)
    collector.stop()


def _emit_unused_warning(relation: UnusedRelation) -> None:
    """
    Emit a single UnusedRelatedAccess warning with a descriptive message.

    Args:
        relation: The loaded-but-not-consumed relation to warn about, carrying its kind,
            cache name, model name, and call-site location.
    """
    location_suffix = f" Queryset marked at {relation.location}." if relation.location else ""

    warnings.warn(
        f'{relation.kind}("{relation.cache_name}") was loaded but never accessed on '
        f"<{relation.model_name} instance>.{location_suffix}",
        category=UnusedRelatedAccess,
        stacklevel=2,
    )
