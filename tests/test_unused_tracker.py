from eagle import unused


class TestEndRequestInactive:
    def test_end_request_is_noop_when_not_active(self) -> None:
        assert unused.is_active() is False
        unused.end_request()
        assert unused.is_active() is False
