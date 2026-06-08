import asyncio

import pytest

import eagle
from eagle import mark_considered, may_access
from test_project.models import Eagle
from tests.base import (
    InactiveCollectorTestBase,
    MayAccessHelperTestBase,
    BaseRequestTest,
)


class TestMayAccess(BaseRequestTest):
    def test_may_access_suppresses_when_called(self):
        warns = self.request(select_related="location", may_access="location", may_access_call="1")
        assert warns == []

    def test_may_access_does_not_suppress_when_not_called(self):
        warns = self.request(select_related="location", may_access="location")
        assert len(warns) == 1
        assert 'select_related("location")' in str(warns[0])

    def test_may_access_multiple_fields(self):
        warns = self.request(
            select_related="location",
            prefetch_related="previous_locations",
            may_access="location,previous_locations",
            may_access_call="1",
        )
        assert warns == []

    def test_may_access_does_not_mark_when_wrapped_raises(self):
        warns = self.request(
            select_related="location",
            may_access="location",
            may_access_call="1",
            may_access_raise="1",
        )
        assert len(warns) == 1
        assert 'select_related("location")' in str(warns[0])


class TestPublicExport:
    def test_public_exports(self):
        assert eagle.may_access is may_access
        assert eagle.mark_considered is mark_considered


class TestMayAccessHelper(MayAccessHelperTestBase):
    def test_may_access_async_function_suppresses_after_await(self):
        Eagle.objects.select_related("location").get()

        @may_access(Eagle, "location")
        async def consumer():
            return 7

        assert asyncio.run(consumer()) == 7
        assert self.flush() == []

    def test_may_access_async_function_no_mark_when_raises(self):
        Eagle.objects.select_related("location").get()

        class Boom(Exception):
            pass

        @may_access(Eagle, "location")
        async def consumer():
            raise Boom

        with pytest.raises(Boom):
            asyncio.run(consumer())
        assert len(self.flush()) == 1


class TestMayAccessInactiveCollector(InactiveCollectorTestBase):
    def test_mark_considered_inactive_is_noop(self):
        mark_considered(Eagle, "location")
        mark_considered("Eagle", "location", "previous_locations")

    def test_may_access_inactive_is_noop(self):
        @may_access(Eagle, "location")
        def consumer(x):
            return x * 2

        assert consumer(3) == 6

    def test_may_access_async_inactive_is_noop(self):
        @may_access(Eagle, "location")
        async def consumer(x):
            return x * 2

        assert asyncio.run(consumer(3)) == 6
