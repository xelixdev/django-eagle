from django.apps import apps as django_apps
from django.test import override_settings

import eagle.instrumentation as instrumentation


class TestEagleAppConfigReady:
    def test_ready_is_noop_when_disabled(self, monkeypatch: object) -> None:
        calls: list[str] = []
        monkeypatch.setattr(instrumentation, "patch_orm", lambda: calls.append("patch_orm"))
        monkeypatch.setattr(instrumentation, "register_tracked_models", lambda models: calls.append("register"))

        with override_settings(EAGLE_ENABLED=False):
            django_apps.get_app_config("eagle").ready()

        assert calls == []

    def test_ready_skips_contenttypes_eager_when_app_config_missing(self, monkeypatch: object) -> None:
        calls: list[str] = []
        monkeypatch.setattr(instrumentation, "make_contenttypes_eager", lambda: calls.append("contenttypes"))

        original_get_app_config = django_apps.get_app_config

        def fake_get_app_config(label: str) -> object:
            if label == "contenttypes":
                msg = "contenttypes"
                raise LookupError(msg)
            return original_get_app_config(label)

        eagle_config = original_get_app_config("eagle")
        monkeypatch.setattr(django_apps, "get_app_config", fake_get_app_config)

        eagle_config.ready()

        assert calls == []
