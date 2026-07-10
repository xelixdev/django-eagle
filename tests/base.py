from dataclasses import dataclass

import pytest
from rest_framework.test import APIClient

from eagle import unused
from excluded_app.models import Burrow
from test_project.models import Aerie, Climate, Eagle, Eaglet, Location, Sighting
from tests.factories import (
    AerieFactory,
    BurrowFactory,
    ClimateFactory,
    EagleFactory,
    EagletFactory,
    LocationFactory,
    SightingFactory,
)


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
class EagleFixtureMixin:
    """Supplies a plain ``eagle`` fixture to any test class that needs a single tracked instance."""

    @pytest.fixture
    def eagle(self) -> Eagle:
        """Create a single eagle via the default factory."""
        return EagleFactory()


class AerieFixtureMixin(EagleFixtureMixin):
    """Supplies an ``aerie`` fixture: a non-nullable forward one-to-one owned by the eagle fixture."""

    @pytest.fixture
    def aerie(self, eagle: Eagle) -> Aerie:
        """Create an Aerie whose forward one-to-one points at the eagle fixture."""
        return AerieFactory(eagle=eagle)


class BurrowFixtureMixin(EagleFixtureMixin):
    """Supplies a ``burrow`` fixture: a reverse one-to-one from excluded_app, owned by the eagle fixture."""

    @pytest.fixture
    def burrow(self, eagle: Eagle) -> Burrow:
        """Create a Burrow (an excluded_app model) whose one-to-one points at the eagle fixture."""
        return BurrowFactory(eagle=eagle)


class SightingFixtureMixin(EagleFixtureMixin):
    """Supplies a ``sighting`` fixture: a GenericForeignKey pointing at the eagle fixture."""

    @pytest.fixture
    def sighting(self, eagle: Eagle) -> Sighting:
        """Create a Sighting whose content_object GenericForeignKey resolves to the eagle fixture."""
        return SightingFactory(content_object=eagle)


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
