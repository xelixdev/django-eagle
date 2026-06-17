import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings

from eagle import UnusedRelatedAccess, unused
from eagle.panels import EagleUnusedLoadsPanel, _row_estimate, build_panel_stats
from eagle.unused import UnusedRelation
from test_project.models import Eagle, Location
from tests.factories import EagleFactory, LocationFactory


def _select_related(instances=10, columns=8, warn_ignored=False):
    return UnusedRelation(
        model_label="test_project.Eagle",
        model_name="Eagle",
        cache_name="location",
        kind="select_related",
        location="app/views.py:5",
        instances=instances,
        columns=columns,
        warn_ignored=warn_ignored,
    )


def _prefetch_related(instances=4, warn_ignored=False):
    return UnusedRelation(
        model_label="test_project.Eagle",
        model_name="Eagle",
        cache_name="previous_locations",
        kind="prefetch_related",
        location="app/views.py:9",
        instances=instances,
        columns=None,
        warn_ignored=warn_ignored,
    )


class TestRowEstimate:
    """The per-row estimate string reflects the kind and the known magnitude."""

    def test_select_related_with_magnitude(self):
        assert _row_estimate(_select_related(instances=120, columns=8)) == "1 JOIN · ~120×8 cells"

    def test_select_related_without_columns(self):
        assert _row_estimate(_select_related(instances=120, columns=None)) == "1 JOIN"

    def test_select_related_zero_instances(self):
        assert _row_estimate(_select_related(instances=0, columns=8)) == "1 JOIN"

    def test_prefetch_related_with_parents(self):
        assert _row_estimate(_prefetch_related(instances=120)) == "1 query · 120 parents"

    def test_prefetch_related_without_parents(self):
        assert _row_estimate(_prefetch_related(instances=0)) == "1 query"


class TestBuildPanelStats:
    """build_panel_stats aggregates a report into template context with headline estimates."""

    def test_mixed_report(self):
        stats = build_panel_stats(
            [_select_related(instances=10, columns=8), _prefetch_related(instances=4)], enabled=True
        )

        assert stats["enabled"] is True
        assert stats["count"] == 2
        assert stats["by_kind"] == {"select_related": 1, "prefetch_related": 1}
        assert stats["estimated"] == {"extra_joins": 1, "extra_queries": 1, "wasted_cells": 80}
        assert [row["estimate"] for row in stats["relations"]] == ["1 JOIN · ~10×8 cells", "1 query · 4 parents"]
        assert stats["suppressed"] == 0
        assert [row["warn_ignored"] for row in stats["relations"]] == [False, False]

    def test_warning_suppressed_rows_are_counted_and_flagged(self):
        stats = build_panel_stats([_select_related(warn_ignored=True), _prefetch_related()], enabled=True)

        assert stats["count"] == 2
        assert stats["suppressed"] == 1
        assert [row["warn_ignored"] for row in stats["relations"]] == [True, False]

    def test_disabled_shape(self):
        stats = build_panel_stats([], enabled=False)

        assert stats["enabled"] is False
        assert stats["count"] == 0
        assert stats["by_kind"] == {"select_related": 0, "prefetch_related": 0}
        assert stats["estimated"] == {"extra_joins": 0, "extra_queries": 0, "wasted_cells": 0}
        assert stats["relations"] == []

    def test_empty_enabled_shape(self):
        stats = build_panel_stats([], enabled=True)

        assert stats["enabled"] is True
        assert stats["count"] == 0
        assert stats["relations"] == []


class _StubStore:
    """Minimal Debug Toolbar store: record_stats persists through here, but the panel reads toolbar.stats."""

    def save_panel(self, request_id, panel_id, stats):
        pass


class _StubToolbar:
    """Just enough of the Debug Toolbar surface for a panel to record and read its own stats."""

    def __init__(self, request):
        self.stats = {}
        self.store = _StubStore()
        self.request_id = "test-request"
        self.request = request


@pytest.mark.django_db
class TestPanelLifecycle:
    """Driving process_request -> generate_stats records the request's unused loads on the panel."""

    def _make_panel(self, get_response):
        request = RequestFactory().get("/")
        panel = EagleUnusedLoadsPanel(_StubToolbar(request), get_response)
        return panel, request

    def test_standalone_unused_load_is_recorded(self):
        EagleFactory(location=LocationFactory())

        def get_response(request):
            # No Eagle middleware in play, so the panel owns the scope; load but never read.
            list(Eagle.objects.select_related("location"))
            return HttpResponse()

        panel, request = self._make_panel(get_response)
        panel.process_request(request)
        with pytest.warns(UnusedRelatedAccess):
            panel.generate_stats(request, HttpResponse())

        stats = panel.get_stats()
        assert stats["enabled"] is True
        assert stats["count"] == 1
        assert stats["relations"][0]["field"] == "location"
        assert stats["relations"][0]["columns"] == len(Location._meta.concrete_fields)
        assert panel.nav_subtitle == "1 unused"
        assert not unused.is_active()

    def test_middleware_outside_panel_reads_live_collector(self):
        # Eagle's middleware wraps the toolbar: the scope is already open when the panel runs,
        # and is still live at generate_stats, so the panel reads the collector directly.
        EagleFactory(location=LocationFactory())
        unused.begin_request()

        def get_response(request):
            list(Eagle.objects.select_related("location"))
            return HttpResponse()

        panel, request = self._make_panel(get_response)
        panel.process_request(request)
        panel.generate_stats(request, HttpResponse())

        assert panel.get_stats()["count"] == 1
        # The outer middleware -- not the panel -- ends the scope and emits the warning.
        with pytest.warns(UnusedRelatedAccess):
            unused.end_request()
        assert not unused.is_active()

    def test_middleware_inside_panel_reads_stashed_report(self):
        # Eagle's middleware runs inside the toolbar: by generate_stats the scope has already
        # ended and stashed its report, so the panel reads the stash rather than a live collector.
        EagleFactory(location=LocationFactory())
        unused.begin_request()

        panel, request = self._make_panel(lambda request: HttpResponse())
        panel.process_request(request)

        with pytest.warns(UnusedRelatedAccess):  # noqa: PT031
            list(Eagle.objects.select_related("location"))
            unused.end_request()

        panel.generate_stats(request, HttpResponse())

        assert panel.get_stats()["count"] == 1
        assert not unused.is_active()

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"model": "Eagle", "field": "location"}])
    def test_warning_suppressed_load_still_shown_without_warning(self):
        EagleFactory(location=LocationFactory())

        def get_response(request):
            list(Eagle.objects.select_related("location"))
            return HttpResponse()

        panel, request = self._make_panel(get_response)
        panel.process_request(request)
        # The relation is warning-suppressed, so ending the scope emits nothing...
        panel.generate_stats(request, HttpResponse())

        # ...but the panel still surfaces it, flagged as suppressed.
        stats = panel.get_stats()
        assert stats["count"] == 1
        assert stats["suppressed"] == 1
        assert stats["relations"][0]["warn_ignored"] is True
        assert not unused.is_active()

    @override_settings(EAGLE_DEBUG_TOOLBAR_IGNORE=[{"model": "Eagle", "field": "location"}])
    def test_toolbar_ignored_load_hidden_but_still_warns(self):
        EagleFactory(location=LocationFactory())

        def get_response(request):
            list(Eagle.objects.select_related("location"))
            return HttpResponse()

        panel, request = self._make_panel(get_response)
        panel.process_request(request)
        # The relation is NOT warning-suppressed, so the warning still fires...
        with pytest.warns(UnusedRelatedAccess):
            panel.generate_stats(request, HttpResponse())

        # ...but the toolbar ignore list hides it from the panel.
        stats = panel.get_stats()
        assert stats["count"] == 0
        assert panel.nav_subtitle == "0 unused"
        assert not unused.is_active()

    @override_settings(EAGLE_ENABLED=False)
    def test_disabled_records_disabled_stats(self):
        panel, request = self._make_panel(lambda request: HttpResponse())
        panel.process_request(request)
        panel.generate_stats(request, HttpResponse())

        stats = panel.get_stats()
        assert stats["enabled"] is False
        assert stats["count"] == 0
        assert panel.nav_subtitle == "0 unused"
        assert not unused.is_active()
