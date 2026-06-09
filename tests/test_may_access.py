import asyncio

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

import eagle
from eagle import UnusedRelatedAccess, mark_considered, may_access, unused
from test_project.models import Eagle
from tests.base import (
    BaseRequestTest,
    EagleGraph,
    EagleWithLocation,
    InactiveCollectorTestBase,
    MayAccessHelperTestBase,
)


class TestMayAccess(BaseRequestTest):
    def test_may_access_suppresses_when_called(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(url, {"select_related": "location", "may_access": "location", "may_access_call": "1"})
        assert response.status_code == 200

    def test_may_access_does_not_suppress_when_not_called(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(url, {"select_related": "location", "may_access": "location"})
        assert 'select_related("location")' in str(exc_info.value)

    def test_may_access_multiple_fields(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        response = api_client.get(
            url,
            {
                "select_related": "location",
                "prefetch_related": "previous_locations",
                "may_access": "location,previous_locations",
                "may_access_call": "1",
            },
        )
        assert response.status_code == 200

    def test_may_access_does_not_mark_when_wrapped_raises(self, api_client: APIClient, eagle_graph: EagleGraph):
        url = reverse("eagle-detail", kwargs={"pk": eagle_graph.eagle.pk})
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            api_client.get(
                url,
                {
                    "select_related": "location",
                    "may_access": "location",
                    "may_access_call": "1",
                    "may_access_raise": "1",
                },
            )
        assert 'select_related("location")' in str(exc_info.value)


class TestPublicExport:
    def test_public_exports(self):
        assert eagle.may_access is may_access
        assert eagle.mark_considered is mark_considered


class TestMayAccessHelper(MayAccessHelperTestBase):
    def test_may_access_async_function_suppresses_after_await(self, eagle_with_location: EagleWithLocation):
        Eagle.objects.select_related("location").get()

        @may_access(Eagle, "location")
        async def consumer():
            return 7

        assert asyncio.run(consumer()) == 7
        # location was marked accessed after the await, so ending the request emits no warning (no error).
        unused.end_request()

    def test_may_access_async_function_no_mark_when_raises(self, eagle_with_location: EagleWithLocation):
        Eagle.objects.select_related("location").get()

        class Boom(Exception):
            pass

        @may_access(Eagle, "location")
        async def consumer():
            raise Boom

        with pytest.raises(Boom):
            asyncio.run(consumer())
        # The wrapped function raised before marking, so the loaded relation is still unused.
        with pytest.raises(UnusedRelatedAccess):
            unused.end_request()


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
