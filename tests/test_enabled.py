from django.test import override_settings

from eagle.config import is_enabled
from tests.base import BaseRequestTest


class TestEnabledDefault:
    def test_enabled_by_default(self):
        assert is_enabled() is True

    @override_settings(EAGLE_ENABLED=False)
    def test_disabled_when_setting_false(self):
        assert is_enabled() is False


class TestDisabledRequest(BaseRequestTest):
    @override_settings(EAGLE_ENABLED=False)
    def test_unused_eager_load_does_not_warn_when_disabled(self):
        assert self.request(select_related="location") == []

    def test_unused_eager_load_warns_when_enabled(self):
        assert len(self.request(select_related="location")) == 1
