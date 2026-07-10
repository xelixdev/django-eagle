import pytest

from eagle import UnusedRelatedAccess, unused
from test_project.models import Eagle
from tests.base import EagleFixtureMixin


class TestMarkerGuardsOutsideActiveRequest(EagleFixtureMixin):
    def test_marking_functions_are_inert_outside_a_request(self, eagle: Eagle) -> None:
        assert unused.is_active() is False
        unused.mark_select_related(eagle, "_location_cache")
        unused.mark_prefetched([eagle], "previous_locations")
        unused.mark_consumed(eagle, "_location_cache")
        assert unused.is_active() is False

        unused.begin_request()
        unused.init_state(eagle, location=None)
        unused.mark_select_related(eagle, "_location_cache")
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            unused.end_request()
        assert 'select_related("_location_cache")' in str(exc_info.value)

    def test_mark_prefetched_skips_instance_without_initialized_state(self, eagle: Eagle) -> None:
        unused.begin_request()
        unused.mark_prefetched([eagle], "previous_locations")
        unused.end_request()

    def test_second_init_state_call_does_not_overwrite_location(self, eagle: Eagle) -> None:
        unused.begin_request()
        unused.init_state(eagle, location="first-location")
        unused.init_state(eagle, location="second-location")
        unused.mark_select_related(eagle, "_location_cache")
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            unused.end_request()
        message = str(exc_info.value)
        assert "first-location" in message
        assert "second-location" not in message
