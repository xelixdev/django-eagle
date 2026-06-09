import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from eagle import UnusedRelatedAccess
from tests.base import BaseRequestTest, EagleGraph


class TestMarkConsidered(BaseRequestTest):
    def test_mark_considered_suppresses_warning(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "location", "mark_considered": "location"})
        assert response.status_code == 200

    def test_mark_considered_before_query_suppresses(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(
            url, {"select_related": "location", "mark_considered": "location", "mark_before": "1"}
        )
        assert response.status_code == 200

    def test_mark_considered_multiple_cache_names(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(
            url,
            {
                "select_related": "location",
                "prefetch_related": "previous_locations",
                "mark_considered": "location,previous_locations",
            },
        )
        assert response.status_code == 200

    def test_mark_considered_wrong_field_still_warns(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"select_related": "location", "mark_considered": "previous_locations"})
        assert 'select_related("location")' in str(exc_info.value)
