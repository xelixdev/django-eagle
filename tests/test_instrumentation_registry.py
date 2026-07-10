from eagle.instrumentation import registry
from test_project.models import Eagle


class TestRegistryClear:
    def test_clear_removes_all_registered_models(self) -> None:
        original = set(registry._instrumented)
        try:
            assert registry.is_instrumented(Eagle) is True
            registry.clear()
            assert registry.is_instrumented(Eagle) is False
        finally:
            registry.register_tracked_models(original)

        assert registry.is_instrumented(Eagle) is True
