import pytest

from eagle import unused
from test_project import views
from test_project.models import Eagle
from tests.base import (
    BaseRequestTest,
)
from tests.factories import BurrowFactory, ClimateFactory, EagleFactory, LocationFactory


class TestWarnUnusedQuerySet(BaseRequestTest):
    def test_select_related_accessed_no_warning(self):
        assert self.request(select_related="location", access="location") == []

    def test_select_related_unused_warns(self):
        warns = self.request(select_related="location")
        assert len(warns) == 1
        assert 'select_related("location")' in str(warns[0])

    def test_query_outside_request_not_tracked(self):
        assert not unused.is_active()
        Eagle.objects.select_related("location").get()
        assert self.request() == []

    def test_location_captured_in_warning(self):
        warns = self.request(select_related="location")
        assert len(warns) == 1
        assert views.__file__ in str(warns[0])

    def test_prefetch_related_unused_warns(self):
        warns = self.request(prefetch_related="previous_locations")
        assert len(warns) == 1
        assert 'prefetch_related("previous_locations")' in str(warns[0])

    def test_prefetch_related_accessed_no_warning(self):
        assert self.request(prefetch_related="previous_locations", access="previous_locations") == []

    def test_prefetch_related_raw_cache_read_no_warning(self):
        assert self.request(prefetch_related="previous_locations", access="previous_locations_raw") == []

    def test_reverse_o2o_cached_none_unused_warns(self):
        eagle_no_eaglet = EagleFactory(location=None, weight=50)
        warns = self.request(pk=eagle_no_eaglet.pk, select_related="eaglet")
        assert len(warns) == 1
        assert 'select_related("eaglet")' in str(warns[0])

    def test_reverse_o2o_exists_accessed_no_warning(self):
        assert self.request(select_related="eaglet", access="eaglet") == []

    def test_reverse_o2o_exists_unused_warns(self):
        warns = self.request(select_related="eaglet")
        assert len(warns) == 1
        assert 'select_related("eaglet")' in str(warns[0])

    def test_reverse_o2o_from_excluded_app_accessed_no_warning(self):
        BurrowFactory(eagle=self.graph.eagle)
        assert self.request(select_related="burrow", access="burrow") == []

    def test_reverse_o2o_from_excluded_app_unused_warns(self):
        BurrowFactory(eagle=self.graph.eagle)
        warns = self.request(select_related="burrow")
        assert len(warns) == 1
        assert 'select_related("burrow")' in str(warns[0])


class TestWarnUnusedToAttrPrefetch(BaseRequestTest):
    def test_to_attr_prefetch_accessed_no_warning(self):
        assert self.request(prefetch_to_attr="previous_locations:prev", access="to_attr") == []

    def test_to_attr_prefetch_unused_warns(self):
        warns = self.request(prefetch_to_attr="previous_locations:prev")
        assert len(warns) == 1
        assert 'prefetch_related("previous_locations")' in str(warns[0])

    def test_to_attr_prefetch_with_rows_accessed_no_warning(self):
        previous = LocationFactory()
        self.graph.eagle.previous_locations.add(previous)
        assert self.request(prefetch_to_attr="previous_locations:prev", access="to_attr") == []


class TestWarnUnusedNestedPrefetch(BaseRequestTest):
    @pytest.fixture
    def previous_location_with_climate(self):
        # Give the eagle a previous location that itself has a climate, so a
        # ``previous_locations__climates__locations`` chain has rows at every depth.
        previous = LocationFactory(climates=[ClimateFactory()])
        self.graph.eagle.previous_locations.add(previous)
        return previous

    def test_nested_prefetched_child_unused_warns_with_propagated_location(self, previous_location_with_climate):
        warns = self.request(
            prefetch_related="previous_locations__climates",
            access="previous_locations",
        )

        assert len(warns) == 1
        assert 'prefetch_related("climates")' in str(warns[0])
        assert "<Location instance>" in str(warns[0])
        assert views.__file__ in str(warns[0])

    def test_depth_three_nested_prefetch_unused_warns(self, previous_location_with_climate):
        # Prefetch three levels deep but stop reading at the climate level: the
        # deepest reverse-M2M (``Climate.locations``) is loaded but never accessed.
        warns = self.request(
            prefetch_related="previous_locations__climates__locations",
            access="previous_locations__climates",
        )

        assert len(warns) == 1
        assert 'prefetch_related("locations")' in str(warns[0])
        assert "<Climate instance>" in str(warns[0])
        assert views.__file__ in str(warns[0])

    def test_depth_three_nested_prefetch_accessed_no_warning(self, previous_location_with_climate):
        assert (
            self.request(
                prefetch_related="previous_locations__climates__locations",
                access="previous_locations__climates__locations",
            )
            == []
        )


class TestWarnUnusedSelectRelatedWithinPrefetch(BaseRequestTest):
    def test_select_related_within_prefetch_queryset_unused_warns(self):
        # Prefetch("eaglet", queryset=Eaglet.objects.select_related("eagle")): the prefetched
        # eaglet is read, but the select_related FK back to its eagle never is.
        warns = self.request(prefetch_select="eaglet:eagle", access="eaglet")

        assert len(warns) == 1
        assert 'select_related("eagle")' in str(warns[0])
        assert "<Eaglet instance>" in str(warns[0])
        assert views.__file__ in str(warns[0])

    def test_select_related_within_prefetch_queryset_accessed_no_warning(self):
        assert self.request(prefetch_select="eaglet:eagle", access="eaglet__eagle") == []
