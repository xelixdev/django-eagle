from django.contrib.auth.models import Group
from django.test import override_settings

from eagle.instrumentation import scope
from test_project.models import Eagle


class TestScope:
    def _instrumented_models(self) -> set:
        return set(scope.get_first_party_models())

    def test_first_party_app_instrumented_by_default(self):
        assert Eagle in self._instrumented_models()

    def test_third_party_app_skipped_by_default(self):
        assert Group not in self._instrumented_models()

    @override_settings(EAGLE_EXCLUDE_APPS=["test_project"])
    def test_excluded_first_party_app_skipped(self):
        assert Eagle not in self._instrumented_models()

    @override_settings(EAGLE_THIRD_PARTY_INCLUDE_APPS=["django.contrib.auth"])
    def test_third_party_app_instrumented_with_include(self):
        assert Group in self._instrumented_models()

    @override_settings(
        EAGLE_THIRD_PARTY_INCLUDE_APPS=["django.contrib.auth"],
        EAGLE_EXCLUDE_APPS=["django.contrib.auth.auth"],
    )
    def test_exclude_wins_over_third_party_include(self):
        assert Group not in self._instrumented_models()

    @override_settings(
        EAGLE_THIRD_PARTY_INCLUDE_APPS=["django.contrib.auth"],
        EAGLE_EXCLUDE_APPS=["auth"],
    )
    def test_bare_label_does_not_exclude_third_party(self):
        assert Group in self._instrumented_models()
