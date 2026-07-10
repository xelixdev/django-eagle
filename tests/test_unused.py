import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from eagle import UnusedRelatedAccess, unused, warn_unused
from excluded_app.models import Burrow
from test_project import views
from test_project.models import Aerie, Eagle, Location
from tests.base import BaseRequestTest, EagleGraph
from tests.factories import AerieFactory, BurrowFactory, ClimateFactory, EagleFactory, LocationFactory


class TestWarnUnusedQuerySet(BaseRequestTest):
    def test_select_related_accessed_no_warning(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "location", "access": "location"})
        assert response.status_code == 200

    def test_select_related_unused_warns(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"select_related": "location"})
        assert 'select_related("location")' in str(exc_info.value)

    def test_query_outside_request_not_tracked(self, api_client: APIClient, eagle_graph: EagleGraph):
        assert not unused.is_active()
        Eagle.objects.select_related("location").get()
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url)
        assert response.status_code == 200

    def test_location_captured_in_warning(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"select_related": "location"})
        assert views.__file__ in str(exc_info.value)

    def test_prefetch_related_unused_warns(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"prefetch_related": "previous_locations"})
        assert 'prefetch_related("previous_locations")' in str(exc_info.value)

    def test_prefetch_related_accessed_no_warning(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"prefetch_related": "previous_locations", "access": "previous_locations"})
        assert response.status_code == 200

    def test_prefetch_related_raw_cache_read_no_warning(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"prefetch_related": "previous_locations", "access": "previous_locations_raw"})
        assert response.status_code == 200

    def test_reverse_o2o_cached_none_unused_warns(self, api_client: APIClient):
        eagle_no_eaglet = EagleFactory(location=None, weight=50)
        url = reverse("eagle-detail", kwargs={"pk": eagle_no_eaglet.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"select_related": "eaglet"})
        assert 'select_related("eaglet")' in str(exc_info.value)

    def test_reverse_o2o_exists_accessed_no_warning(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "eaglet", "access": "eaglet"})
        assert response.status_code == 200

    def test_reverse_o2o_exists_unused_warns(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"select_related": "eaglet"})
        assert 'select_related("eaglet")' in str(exc_info.value)

    def test_reverse_o2o_from_excluded_app_accessed_no_warning(self, api_client: APIClient, eagle_graph: EagleGraph):
        BurrowFactory(eagle=eagle_graph.eagle)
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "burrow", "access": "burrow"})
        assert response.status_code == 200

    def test_reverse_o2o_from_excluded_app_unused_warns(self, api_client: APIClient, eagle_graph: EagleGraph):
        BurrowFactory(eagle=eagle_graph.eagle)
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"select_related": "burrow"})
        assert 'select_related("burrow")' in str(exc_info.value)


class TestWarnUnusedToAttrPrefetch(BaseRequestTest):
    def test_to_attr_prefetch_accessed_no_warning(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"prefetch_to_attr": "previous_locations:prev", "access": "to_attr"})
        assert response.status_code == 200

    def test_to_attr_prefetch_unused_warns(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"prefetch_to_attr": "previous_locations:prev"})
        assert 'prefetch_related("previous_locations")' in str(exc_info.value)

    def test_to_attr_prefetch_with_rows_accessed_no_warning(self, api_client: APIClient, eagle_graph: EagleGraph):
        eagle_graph.eagle.previous_locations.add(LocationFactory())
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"prefetch_to_attr": "previous_locations:prev", "access": "to_attr"})
        assert response.status_code == 200


class TestWarnUnusedNestedPrefetch(BaseRequestTest):
    @pytest.fixture
    def previous_location_with_climate(self, eagle_graph: EagleGraph) -> Location:
        # Give the eagle a previous location that itself has a climate, so a
        # ``previous_locations__climates__locations`` chain has rows at every depth.
        previous = LocationFactory(climates=[ClimateFactory()])
        eagle_graph.eagle.previous_locations.add(previous)
        return previous

    def test_nested_prefetched_child_unused_warns_with_propagated_location(
        self, api_client: APIClient, eagle_graph: EagleGraph, previous_location_with_climate: Location
    ):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"prefetch_related": "previous_locations__climates", "access": "previous_locations"})

        message = str(exc_info.value)
        assert 'prefetch_related("climates")' in message
        assert "<Location instance>" in message
        assert views.__file__ in message

    def test_depth_three_nested_prefetch_unused_warns(
        self, api_client: APIClient, eagle_graph: EagleGraph, previous_location_with_climate: Location
    ):
        # Prefetch three levels deep but stop reading at the climate level: the
        # deepest reverse-M2M (``Climate.locations``) is loaded but never accessed.
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(
                url,
                {
                    "prefetch_related": "previous_locations__climates__locations",
                    "access": "previous_locations__climates",
                },
            )

        message = str(exc_info.value)
        assert 'prefetch_related("locations")' in message
        assert "<Climate instance>" in message
        assert views.__file__ in message

    def test_depth_three_nested_prefetch_accessed_no_warning(
        self, api_client: APIClient, eagle_graph: EagleGraph, previous_location_with_climate: Location
    ):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(
            url,
            {
                "prefetch_related": "previous_locations__climates__locations",
                "access": "previous_locations__climates__locations",
            },
        )
        assert response.status_code == 200


class TestWarnUnusedSelectRelatedWithinPrefetch(BaseRequestTest):
    def test_select_related_within_prefetch_queryset_unused_warns(self, api_client: APIClient, eagle_graph: EagleGraph):
        # Prefetch("eaglet", queryset=Eaglet.objects.select_related("eagle")): the prefetched
        # eaglet is read, but the select_related FK back to its eagle never is.
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"prefetch_select": "eaglet:eagle", "access": "eaglet"})

        message = str(exc_info.value)
        assert 'select_related("eagle")' in message
        assert "<Eaglet instance>" in message
        assert views.__file__ in message

    def test_select_related_within_prefetch_queryset_accessed_no_warning(
        self, api_client: APIClient, eagle_graph: EagleGraph
    ):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"prefetch_select": "eaglet:eagle", "access": "eaglet__eagle"})
        assert response.status_code == 200


class TestWarnUnusedUnrestrictedSelectRelated(BaseRequestTest):
    @pytest.fixture
    def aerie(self, eagle_graph: EagleGraph) -> Aerie:
        return AerieFactory(eagle=eagle_graph.eagle)

    def test_bare_select_related_auto_discovers_forward_relation_unused(self, aerie: Aerie):
        with pytest.raises(UnusedRelatedAccess) as exc_info, warn_unused():
            Aerie.objects.select_related().get(pk=aerie.pk)
        assert 'select_related("eagle")' in str(exc_info.value)

    def test_bare_select_related_auto_discovers_forward_relation_accessed(self, aerie: Aerie):
        with warn_unused():
            fetched = Aerie.objects.select_related().get(pk=aerie.pk)
            assert fetched.eagle == aerie.eagle


class TestWarnUnusedNestedThroughUninstrumentedOwner(BaseRequestTest):
    @pytest.fixture
    def burrow(self, eagle_graph: EagleGraph) -> Burrow:
        return BurrowFactory(eagle=eagle_graph.eagle)

    def test_relation_owned_by_excluded_app_model_still_recurses(self, burrow: Burrow, eagle_graph: EagleGraph):
        with pytest.raises(UnusedRelatedAccess) as exc_info, warn_unused():
            Eagle.objects.select_related("burrow__eagle").get(pk=eagle_graph.eagle.pk)
        assert 'select_related("burrow")' in str(exc_info.value)
