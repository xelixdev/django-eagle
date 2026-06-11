from dataclasses import dataclass

import pytest
from rest_framework.test import APIClient

from eagle import unused
from test_project.models import Climate, Eagle, Eaglet, Location
from tests.factories import ClimateFactory, EagleFactory, EagletFactory, LocationFactory


@dataclass(frozen=True)
class EagleGraph:
    """A connected set of rows: a location with one climate, an eagle living there, and its eaglet."""

    location: Location
    climate: Climate
    eagle: Eagle
    eaglet: Eaglet


@dataclass(frozen=True)
class EagleWithLocation:
    """An eagle paired with the location it lives in."""

    location: Location
    eagle: Eagle


@pytest.mark.django_db
class EagleGraphMixin:
    """Supplies the ``eagle_graph`` fixture to any test class that eager-loads eagle relations."""

    @pytest.fixture
    def eagle_graph(self, db: None) -> EagleGraph:
        """Build a fully connected eagle graph whose relations a request can eager-load."""
        location = LocationFactory(climates=[ClimateFactory()])
        eagle = EagleFactory(location=location)
        eaglet = EagletFactory(eagle=eagle)
        return EagleGraph(
            location=location,
            climate=location.climates.get(),
            eagle=eagle,
            eaglet=eaglet,
        )


class BaseRequestTest(EagleGraphMixin):
    """Base for tests that drive the eagle detail endpoint; an unused eager load surfaces as an error."""

    @pytest.fixture
    def api_client(self) -> APIClient:
        """Return a DRF test client for calling the eagle endpoints."""
        return APIClient()


@pytest.mark.django_db
class MayAccessHelperTestBase:
    """Base for tests of the may_access/mark_considered helpers run inside a tracking request."""

    @pytest.fixture
    def eagle_with_location(self, db: None) -> EagleWithLocation:
        """Create a single eagle and the location it lives in."""
        location = LocationFactory()
        eagle = EagleFactory(location=location)
        return EagleWithLocation(location=location, eagle=eagle)

    @pytest.fixture(autouse=True)
    def active_request(self) -> None:
        """Open a tracking request before each test; the global reset fixture closes it afterwards."""
        unused.begin_request()


class InactiveCollectorTestBase:
    """Base for tests that must run with no active tracking request."""

    @pytest.fixture(autouse=True)
    def inactive_collector(self) -> None:
        """Ensure no tracking request is active before the test body runs."""
        if unused.is_active():
            unused.end_request()
