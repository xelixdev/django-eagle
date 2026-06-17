from debug_toolbar.panels import Panel
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from eagle import unused
from eagle.config import is_enabled
from eagle.unused import UnusedRelation
from eagle.unused.ignore import should_ignore


def _row_estimate(relation: UnusedRelation) -> str:
    """
    Build the per-row cost estimate string shown in the panel for *relation*.

    Args:
        relation: The unused relation to summarise.

    Returns:
        For select_related, ``"1 JOIN"`` plus a ``"~<instances>×<columns> cells"`` materialisation
        estimate when both are known; for prefetch_related, ``"1 query"`` plus the parent fan-out.
    """
    if relation.kind == "select_related":
        estimate = "1 JOIN"
        if relation.columns is not None and relation.instances:
            estimate = f"{estimate} · ~{relation.instances}×{relation.columns} cells"
        return estimate

    estimate = "1 query"
    if relation.instances:
        estimate = f"{estimate} · {relation.instances} parents"
    return estimate


def _toolbar_ignored(relation: UnusedRelation) -> bool:
    """
    Return True if ``EAGLE_DEBUG_TOOLBAR_IGNORE`` hides *relation* from the panel.

    This is the panel's own ignore list, independent of ``EAGLE_WARN_UNUSED_IGNORE``; it defaults
    to empty, so by default the panel shows every unused load (including warning-suppressed ones).

    Args:
        relation: The unused relation being considered for display.

    Returns:
        True when a configured toolbar ignore rule matches the relation.
    """
    rules = getattr(settings, "EAGLE_DEBUG_TOOLBAR_IGNORE", [])
    return should_ignore(relation.model_name, relation.cache_name, relation.location, rules)


def build_panel_stats(report: list[UnusedRelation], *, enabled: bool) -> dict:
    """
    Turn an unused-relation report into Debug Toolbar template context with cost estimates.

    Args:
        report: The relations to display (already filtered by the panel's own ignore list).
        enabled: Whether Eagle is enabled; drives the panel's disabled message.

    Returns:
        A context dict with the total ``count``, the number of shown rows currently
        warning-suppressed (``suppressed``), a ``by_kind`` split, headline ``estimated`` tallies
        (extra JOINs, extra queries, wasted cells), and a ``relations`` list of per-row dicts
        (model, field, kind, location, instances, columns, estimate, warn_ignored).
    """
    select_related = [relation for relation in report if relation.kind == "select_related"]
    prefetch_related = [relation for relation in report if relation.kind == "prefetch_related"]
    wasted_cells = sum(relation.instances * (relation.columns or 0) for relation in select_related)

    rows = [
        {
            "model": relation.model_name,
            "field": relation.cache_name,
            "kind": relation.kind,
            "location": relation.location,
            "instances": relation.instances,
            "columns": relation.columns,
            "estimate": _row_estimate(relation),
            "warn_ignored": relation.warn_ignored,
        }
        for relation in report
    ]

    return {
        "enabled": enabled,
        "count": len(report),
        "suppressed": sum(1 for relation in report if relation.warn_ignored),
        "by_kind": {"select_related": len(select_related), "prefetch_related": len(prefetch_related)},
        "estimated": {
            "extra_joins": len(select_related),
            "extra_queries": len(prefetch_related),
            "wasted_cells": wasted_cells,
        },
        "relations": rows,
    }


class EagleUnusedLoadsPanel(Panel):
    """Debug Toolbar panel listing eager-loaded relations that were never accessed this request."""

    title = _("Unused Eager Loads")
    template = "eagle/panels/unused_loads.html"

    @property
    def nav_subtitle(self) -> str:  # pyrefly: ignore[bad-override]
        """
        Return the side-bar subtitle: the unused-load count.

        Returns:
            A localised ``"<n> unused"`` string built from the recorded stats.
        """
        count = self.get_stats().get("count", 0)
        return ngettext("%d unused", "%d unused", count) % count

    def process_request(self, request: HttpRequest) -> HttpResponse:
        """
        Open a tracking scope before the view runs, only if Eagle's middleware has not already.

        Args:
            request: The incoming Django HTTP request.

        Returns:
            The response produced by the rest of the middleware/view chain.
        """
        # The panel owns the scope only in standalone use (no Eagle middleware). When the
        # middleware is present it has already begun the request, so we leave it alone.
        self._owns_scope = is_enabled() and not unused.is_active()
        if self._owns_scope:
            unused.begin_request()
        return super().process_request(request)

    def generate_stats(self, request: HttpRequest, response: HttpResponse) -> None:
        """
        Record the unused-loads stats after the response, reading the report order-independently.

        Reads the full report (including warning-suppressed relations) and applies only the
        panel's own ``EAGLE_DEBUG_TOOLBAR_IGNORE`` filter, so suppressed loads stay visible.

        Args:
            request: The Django HTTP request being processed.
            response: The outgoing HTTP response.
        """
        if not is_enabled():
            self.record_stats(build_panel_stats([], enabled=False))
            return

        if getattr(self, "_owns_scope", False) and unused.is_active():
            # Standalone: end the scope we opened (emits warnings + stashes), then read the stash.
            unused.end_request()
            report = unused.get_last_report()
        elif unused.is_active():
            # Eagle's middleware runs outside us, so the collector is still live: read it directly.
            report = unused.collect_all_unused()
        else:
            # Eagle's middleware ran inside us and already ended: read its stashed report.
            report = unused.get_last_report()

        visible = [relation for relation in report if not _toolbar_ignored(relation)]
        self.record_stats(build_panel_stats(visible, enabled=True))
