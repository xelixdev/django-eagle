import traceback

from eagle.unused import location


class TestCaptureLocation:
    def test_returns_none_when_every_frame_is_eagle_or_django(self, monkeypatch: object) -> None:
        fake_frame = traceback.FrameSummary(
            filename=location._EAGLE_DIR + "/instrumentation/query.py", lineno=1, name="f"
        )
        monkeypatch.setattr(traceback, "extract_stack", lambda: [fake_frame, fake_frame, fake_frame, fake_frame])

        assert location.capture_location() is None
