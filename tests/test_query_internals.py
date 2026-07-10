from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db.models import QuerySet

from eagle import unused
from eagle.instrumentation import query
from test_project.models import Aerie, Eagle
from tests.base import EagleFixtureMixin


class TestGetUnrestrictedSelectRelatedGetters:
    def test_returns_nothing_beyond_max_depth(self) -> None:
        getters = list(query.get_unrestricted_select_related_getters(Aerie._meta, max_depth=0))
        assert getters == []


class TestPropagatePrefetchLocation:
    def test_skips_when_child_result_is_not_a_queryset(self) -> None:
        state = SimpleNamespace(warn_unused_location="captured", warn_unused_locations=None)
        instances = [SimpleNamespace(_state=state)]

        query.propagate_prefetch_location(instances, [1, 2, 3], "cache")

    def test_skips_when_child_queryset_already_tagged(self) -> None:
        state = SimpleNamespace(warn_unused_location="captured", warn_unused_locations=None)
        instances = [SimpleNamespace(_state=state)]
        child_queryset = Mock(spec=QuerySet)
        child_queryset._eagle_location = "existing"

        query.propagate_prefetch_location(instances, child_queryset, "cache")

        assert child_queryset._eagle_location == "existing"

    def test_skips_when_resolved_location_is_none(self) -> None:
        state = SimpleNamespace(warn_unused_location=None, warn_unused_locations=None)
        instances = [SimpleNamespace(_state=state)]
        child_queryset = Mock(spec=QuerySet)

        query.propagate_prefetch_location(instances, child_queryset, "cache")

        assert not hasattr(child_queryset, "_eagle_location")


class TestRecordLocations:
    def test_duplicate_names_are_recorded_once(self) -> None:
        clone = SimpleNamespace()

        query._record_locations(clone, iter(["previous_locations", "previous_locations"]))

        assert set(clone._eagle_locations) == {"previous_locations"}


class TestPrefetcherCacheName:
    def test_returns_none_when_prefetcher_has_no_cache_name(self) -> None:
        assert query._prefetcher_cache_name(object()) is None


OPERATIONS = [
    ("len", lambda tracked: len(tracked)),
    ("getitem", lambda tracked: tracked[0]),
    ("contains", lambda tracked: 1 in tracked),
    ("reversed", lambda tracked: list(reversed(tracked))),
    ("eq", lambda tracked: tracked == [1, 2, 3]),
    ("repr", lambda tracked: repr(tracked)),
    ("count", lambda tracked: tracked.count(1)),
    ("index", lambda tracked: tracked.index(1)),
]


class TestTrackedPrefetchListConsumption(EagleFixtureMixin):
    @pytest.mark.parametrize(["label", "operation"], OPERATIONS, ids=[label for label, _ in OPERATIONS])
    def test_operation_marks_prefetch_consumed(self, eagle: Eagle, label: str, operation: object) -> None:
        unused.begin_request()
        unused.init_state(eagle, location=None)
        unused.mark_prefetched([eagle], "previous_locations")
        tracked = query.TrackedPrefetchList([1, 2, 3], eagle, "previous_locations")

        operation(tracked)
        operation(tracked)

        unused.end_request()


class TestEagerPrefetchOneLevel(EagleFixtureMixin):
    def test_inactive_collector_returns_original_result_untouched(self, eagle: Eagle, monkeypatch: object) -> None:
        sentinel = object()
        monkeypatch.setattr(query, "_original_prefetch_one_level", lambda *a: sentinel)
        assert unused.is_active() is False

        result = query._eager_prefetch_one_level([eagle], Mock(), Mock(), 0)

        assert result is sentinel

    def test_no_instances_returns_original_result_untouched(self, monkeypatch: object) -> None:
        sentinel = object()
        monkeypatch.setattr(query, "_original_prefetch_one_level", lambda *a: sentinel)
        unused.begin_request()
        try:
            result = query._eager_prefetch_one_level([], Mock(), Mock(), 0)
        finally:
            unused.end_request()
        assert result is sentinel

    def test_missing_prefetch_cache_name_returns_original_result(self, eagle: Eagle, monkeypatch: object) -> None:
        sentinel = object()
        monkeypatch.setattr(query, "_original_prefetch_one_level", lambda *a: sentinel)
        lookup = Mock(get_current_to_attr=Mock(return_value=("attr", "attr")))
        prefetcher = Mock(spec=[])

        unused.begin_request()
        try:
            result = query._eager_prefetch_one_level([eagle], prefetcher, lookup, 0)
        finally:
            unused.end_request()
        assert result is sentinel

    def test_uninitialized_instance_is_skipped(self, eagle: Eagle, monkeypatch: object) -> None:
        sentinel = object()
        monkeypatch.setattr(query, "_original_prefetch_one_level", lambda *a: sentinel)
        lookup = Mock(get_current_to_attr=Mock(return_value=("attr", "attr")))
        prefetcher = Mock(_prefetch_cache_name=Mock(return_value="cache"))

        unused.begin_request()
        try:
            result = query._eager_prefetch_one_level([eagle], prefetcher, lookup, 0)
        finally:
            unused.end_request()
        assert result is sentinel
        assert not hasattr(eagle, "attr")

    def test_already_tracked_list_is_not_rewrapped(self, eagle: Eagle, monkeypatch: object) -> None:
        monkeypatch.setattr(query, "_original_prefetch_one_level", lambda *a: None)
        lookup = Mock(get_current_to_attr=Mock(return_value=("attr", "attr")))
        prefetcher = Mock(_prefetch_cache_name=Mock(return_value="cache"))

        unused.begin_request()
        unused.init_state(eagle, location=None)
        existing = query.TrackedPrefetchList([1, 2], eagle, "cache")
        eagle.attr = existing

        query._eager_prefetch_one_level([eagle], prefetcher, lookup, 0)
        unused.end_request()

        assert eagle.attr is existing

    def test_single_valued_to_attr_marks_consumed_immediately(self, eagle: Eagle, monkeypatch: object) -> None:
        monkeypatch.setattr(query, "_original_prefetch_one_level", lambda *a: None)
        eagle.attr = None
        lookup = Mock(get_current_to_attr=Mock(return_value=("attr", "attr")))
        prefetcher = Mock(_prefetch_cache_name=Mock(return_value="cache"))

        unused.begin_request()
        unused.init_state(eagle, location=None)
        unused.mark_prefetched([eagle], "cache")

        query._eager_prefetch_one_level([eagle], prefetcher, lookup, 0)

        unused.end_request()
