import importlib
import logging

import eagle.logger as logger_module


class TestLoggerDebugConfig:
    def test_eagle_debug_env_enables_debug_basic_config(self, monkeypatch: object) -> None:
        calls: list[dict] = []
        monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))
        monkeypatch.setenv("EAGLE_DEBUG", "1")

        importlib.reload(logger_module)

        assert calls == [{"level": logging.DEBUG}]

    def test_eagle_debug_unset_skips_basic_config(self, monkeypatch: object) -> None:
        calls: list[dict] = []
        monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: calls.append(kwargs))
        monkeypatch.delenv("EAGLE_DEBUG", raising=False)

        importlib.reload(logger_module)

        assert calls == []
