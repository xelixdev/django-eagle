import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from eagle import UnusedRelatedAccess
from tests.base import BaseRequestTest, EagleGraph


class TestScopeIgnore(BaseRequestTest):
    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"model": "Eagle", "field": "location"}])
    def test_ignore_by_model_and_field(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "location"})
        assert response.status_code == 200

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"field": "location"}])
    def test_ignore_by_field_only(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "location"})
        assert response.status_code == 200

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"model": "Location", "field": "latitude"}])
    def test_ignore_wrong_model_still_warns(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"select_related": "location"})
        assert "location" in str(exc_info.value)

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"location": "*/test_project/*"}])
    def test_ignore_by_location_glob(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "location"})
        assert response.status_code == 200

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"location": "*/test_project/views.py:*"}])
    def test_ignore_by_file_wildcard_glob(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "location"})
        assert response.status_code == 200

    @override_settings(
        EAGLE_WARN_UNUSED_IGNORE=[
            {"model": "Eagle", "field": "location", "location": "*/test_project/*"},
        ]
    )
    def test_ignore_by_all_three_keys_combined(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "location"})
        assert response.status_code == 200
