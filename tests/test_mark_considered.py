from tests.base import BaseRequestTest


class TestMarkConsidered(BaseRequestTest):
    def test_mark_considered_suppresses_warning(self):
        assert self.request(select_related="location", mark_considered="location") == []

    def test_mark_considered_before_query_suppresses(self):
        warns = self.request(select_related="location", mark_considered="location", mark_before="1")
        assert warns == []

    def test_mark_considered_multiple_cache_names(self):
        warns = self.request(
            select_related="location",
            prefetch_related="previous_locations",
            mark_considered="location,previous_locations",
        )
        assert warns == []

    def test_mark_considered_wrong_field_still_warns(self):
        warns = self.request(select_related="location", mark_considered="previous_locations")
        assert len(warns) == 1
        assert 'select_related("location")' in str(warns[0])
