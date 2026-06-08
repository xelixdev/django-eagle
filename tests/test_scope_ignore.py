from django.test import override_settings

from tests.base import BaseRequestTest


class TestScopeIgnore(BaseRequestTest):
    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"model": "Eagle", "field": "location"}])
    def test_ignore_by_model_and_field(self):
        assert self.request(select_related="location") == []

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"field": "location"}])
    def test_ignore_by_field_only(self):
        assert self.request(select_related="location") == []

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"model": "Location", "field": "latitude"}])
    def test_ignore_wrong_model_still_warns(self):
        warns = self.request(select_related="location")
        assert len(warns) == 1
        assert "location" in str(warns[0])

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"location": "*/test_project/*"}])
    def test_ignore_by_location_glob(self):
        assert self.request(select_related="location") == []

    @override_settings(EAGLE_WARN_UNUSED_IGNORE=[{"location": "*/test_project/views.py:*"}])
    def test_ignore_by_file_wildcard_glob(self):
        assert self.request(select_related="location") == []

    @override_settings(
        EAGLE_WARN_UNUSED_IGNORE=[
            {"model": "Eagle", "field": "location", "location": "*/test_project/*"},
        ]
    )
    def test_ignore_by_all_three_keys_combined(self):
        assert self.request(select_related="location") == []
