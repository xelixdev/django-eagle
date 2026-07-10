import sysconfig

from eagle.instrumentation import scope
from test_project.models import Eagle


class TestDependencyRoots:
    def test_skips_paths_missing_from_sysconfig(self, monkeypatch: object) -> None:
        fake_paths = {"purelib": "", "platlib": None, "stdlib": "/fake/stdlib", "platstdlib": "/fake/stdlib"}
        monkeypatch.setattr(sysconfig, "get_paths", lambda: fake_paths)

        roots = scope._dependency_roots()

        assert "/fake/stdlib" in roots


class TestGetFirstPartyModelsProxySkip:
    def test_proxy_models_are_excluded(self) -> None:
        class EagleProxy(Eagle):
            class Meta:
                app_label = "test_project"
                proxy = True

        assert EagleProxy not in set(scope.get_first_party_models())
        assert Eagle in set(scope.get_first_party_models())
