import warnings
from types import SimpleNamespace

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from eagle import UnusedRelatedAccess, unused
from tests.factories import ClimateFactory, EagleFactory, EagletFactory, LocationFactory


@pytest.mark.django_db
class BaseRequestTest:
    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def eagle_graph(self, db):
        location = LocationFactory(climates=[ClimateFactory()])
        eagle = EagleFactory(location=location)
        eaglet = EagletFactory(eagle=eagle)
        return SimpleNamespace(
            location=location,
            climate=location.climates.get(),
            eagle=eagle,
            eaglet=eaglet,
        )

    @pytest.fixture
    def warn_request(self, api_client, eagle_graph):
        def _request(pk=None, **params):
            target = eagle_graph.eagle.pk if pk is None else pk

            url = reverse("eagle-detail", kwargs={"pk": target})

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", UnusedRelatedAccess)
                response = api_client.get(url, params)

            assert response.status_code == 200, response.content
            return [w.message for w in caught if issubclass(w.category, UnusedRelatedAccess)]

        return _request

    @pytest.fixture(autouse=True)
    def setup(self, warn_request, eagle_graph):
        self.request = warn_request
        self.graph = eagle_graph


@pytest.mark.django_db
class MayAccessHelperTestBase:
    @pytest.fixture
    def eagle_with_location(self, db):
        location = LocationFactory()
        eagle = EagleFactory(location=location)
        return SimpleNamespace(location=location, eagle=eagle)

    @pytest.fixture
    def active_request(self):
        unused.begin_request()
        yield
        if unused.is_active():
            unused.end_request()

    @pytest.fixture
    def flush_warnings(self, active_request):
        def _flush():
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", UnusedRelatedAccess)
                unused.end_request()
            unused.begin_request()
            return [w.message for w in caught if issubclass(w.category, UnusedRelatedAccess)]

        return _flush

    @pytest.fixture(autouse=True)
    def setup(self, eagle_with_location, flush_warnings):
        self.data = eagle_with_location
        self.flush = flush_warnings


class InactiveCollectorTestBase:
    @pytest.fixture(autouse=True)
    def inactive_collector(self):
        if unused.is_active():
            unused.end_request()
        yield
