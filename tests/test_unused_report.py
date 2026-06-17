import pytest
from django.test import override_settings

from eagle import UnusedRelatedAccess, unused, warn_unused
from eagle.unused import collect_all_unused, collect_unused, get_last_report
from eagle.unused.report import (
    _related_column_count,
    clear_warn_suppressed_labels,
    register_warn_suppressed_labels,
)
from test_project.models import Eagle, Location
from tests.factories import EagleFactory, LocationFactory


@pytest.mark.django_db
class TestCollectUnused:
    """collect_unused() reports loaded-but-unread relations with their magnitude, via real querysets."""

    def test_select_related_reports_instances_and_columns(self):
        location = LocationFactory()
        for _ in range(3):
            EagleFactory(location=location)

        # Load location on every eagle row but never read it, then inspect the live report
        # before the scope ends and turns the survivor into a warning.
        with pytest.warns(UnusedRelatedAccess), warn_unused():  # noqa: PT031
            list(Eagle.objects.select_related("location"))
            report = collect_unused()

        assert len(report) == 1
        relation = report[0]
        assert relation.kind == "select_related"
        assert relation.model_name == "Eagle"
        assert relation.cache_name == "location"
        assert relation.instances == 3
        assert relation.columns == len(Location._meta.concrete_fields)
        assert relation.location is not None
        assert "test_unused_report.py" in relation.location

    def test_prefetch_related_reports_parent_fanout_and_no_columns(self):
        location = LocationFactory()
        for _ in range(2):
            EagleFactory(location=location)

        with pytest.warns(UnusedRelatedAccess), warn_unused():  # noqa: PT031
            list(Eagle.objects.prefetch_related("previous_locations"))
            report = collect_unused()

        assert len(report) == 1
        relation = report[0]
        assert relation.kind == "prefetch_related"
        assert relation.cache_name == "previous_locations"
        assert relation.columns is None
        assert relation.instances == 2

    def test_consumed_relation_absent_from_report(self):
        eagle = EagleFactory(location=LocationFactory())

        with warn_unused():
            obj = Eagle.objects.select_related("location").get(pk=eagle.pk)
            _ = obj.location
            report = collect_unused()

        assert report == []

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"model": "Eagle", "field": "location"}])
    def test_ignored_relation_absent_from_report(self):
        EagleFactory(location=LocationFactory())

        with warn_unused():
            list(Eagle.objects.select_related("location"))
            report = collect_unused()

        assert report == []

    def test_get_last_report_matches_emitted_records(self):
        EagleFactory(location=LocationFactory())

        with pytest.warns(UnusedRelatedAccess), warn_unused():  # noqa: PT031
            list(Eagle.objects.select_related("location"))
            inside_scope = collect_unused()

        stashed = get_last_report()
        assert stashed == inside_scope
        assert len(stashed) == 1
        assert stashed[0].cache_name == "location"


@pytest.mark.django_db
class TestCollectAllUnused:
    """collect_all_unused() is the full set (incl. warning-suppressed); collect_unused() drops the suppressed."""

    def test_no_ignore_full_set_matches_warning_view(self):
        EagleFactory(location=LocationFactory())

        with pytest.warns(UnusedRelatedAccess), warn_unused():  # noqa: PT031
            list(Eagle.objects.select_related("location"))
            full = collect_all_unused()
            warning_view = collect_unused()

        assert len(full) == 1
        assert full[0].warn_ignored is False
        assert full == warning_view

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"model": "Eagle", "field": "location"}])
    def test_warn_ignored_relation_kept_in_full_set_only(self):
        EagleFactory(location=LocationFactory())

        # No warning is emitted on scope exit because the relation is warning-suppressed.
        with warn_unused():
            list(Eagle.objects.select_related("location"))
            full = collect_all_unused()
            warning_view = collect_unused()

        assert len(full) == 1
        assert full[0].cache_name == "location"
        assert full[0].warn_ignored is True
        assert warning_view == []


@pytest.mark.django_db
class TestWarnSuppressedLabels:
    """Models registered as warn-suppressed (e.g. profiled excluded apps) are reported but never warn."""

    @pytest.fixture
    def eagle_label_warn_suppressed(self):
        register_warn_suppressed_labels(["test_project.Eagle"])
        yield
        clear_warn_suppressed_labels()

    def test_warn_suppressed_model_flagged_and_not_warned(self, eagle_label_warn_suppressed):
        EagleFactory(location=LocationFactory())

        # No warning fires on scope exit because Eagle is registered as warn-suppressed; under
        # filterwarnings=error a stray warning would fail this test instead of passing silently.
        with warn_unused():
            list(Eagle.objects.select_related("location"))
            full = collect_all_unused()
            warning_view = collect_unused()

        assert len(full) == 1
        assert full[0].warn_ignored is True
        assert warning_view == []


class TestRelatedColumnCount:
    """The best-effort column resolver counts a forward relation's columns and falls back to None."""

    def test_forward_relation_counts_related_concrete_fields(self):
        cache_name = Eagle._meta.get_field("location").cache_name
        assert _related_column_count("test_project.Eagle", cache_name) == len(Location._meta.concrete_fields)

    def test_unknown_model_returns_none(self):
        assert _related_column_count("test_project.DoesNotExist", "whatever") is None

    def test_unmatched_cache_name_returns_none(self):
        assert _related_column_count("test_project.Eagle", "no_such_cache") is None


class TestCollectUnusedNoRequest:
    """Outside any tracking scope the collector is empty, so the report is empty."""

    def test_returns_empty_when_no_request_active(self):
        assert not unused.is_active()
        assert collect_unused() == []
