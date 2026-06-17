import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from eagle import UnusedRelatedAccess
from eagle.config import include_excluded_apps_in_toolbar, is_enabled
from tests.base import BaseRequestTest, EagleGraph


class TestEnabledDefault:
    @override_settings(EAGLE_ENABLED=None)
    def test_disabled_by_default(self):
        assert is_enabled() is False

    @override_settings(EAGLE_ENABLED=False)
    def test_disabled_when_setting_false(self):
        assert is_enabled() is False

    @override_settings(EAGLE_ENABLED=True)
    def test_enabled_when_setting_true(self):
        assert is_enabled() is True


class TestIncludeExcludedAppsInToolbar:
    def test_false_by_default(self):
        assert include_excluded_apps_in_toolbar() is False

    @override_settings(EAGLE_DEBUG_TOOLBAR_INCLUDE_EXCLUDED_APPS=True)
    def test_true_when_set(self):
        assert include_excluded_apps_in_toolbar() is True


class TestDisabledRequest(BaseRequestTest):
    @override_settings(EAGLE_ENABLED=False)
    def test_unused_eager_load_does_not_warn_when_disabled(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "location"})
        assert response.status_code == 200

    def test_unused_eager_load_warns_when_enabled(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess):
            api_client.get(url, {"select_related": "location"})
