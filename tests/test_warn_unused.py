import asyncio

import pytest
from django.test import override_settings

import eagle
from eagle import UnusedRelatedAccess, unused, warn_unused
from test_project.models import Eagle
from tests.base import BaseRequestTest, EagleGraph


class TestWarnUnusedSync(BaseRequestTest):
    """The decorator scopes tracking to a single synchronous call, like the middleware does for a request."""

    def test_unused_eager_load_warns(self, eagle_graph: EagleGraph):
        pk = eagle_graph.eagle.pk

        @warn_unused
        def load_unused() -> None:
            # Eager-load location but never read it: the join is wasted.
            Eagle.objects.select_related("location").get(pk=pk)

        with pytest.raises(UnusedRelatedAccess) as exc_info:
            load_unused()
        assert 'select_related("location")' in str(exc_info.value)

    def test_accessed_eager_load_no_warning(self, eagle_graph: EagleGraph):
        pk = eagle_graph.eagle.pk

        @warn_unused
        def load_and_access() -> object:
            eagle = Eagle.objects.select_related("location").get(pk=pk)
            return eagle.location

        # The relation is read before the call returns, so ending the scope emits nothing.
        assert load_and_access() == eagle_graph.location

    def test_collector_inactive_after_call(self, eagle_graph: EagleGraph):
        pk = eagle_graph.eagle.pk

        @warn_unused
        def load_and_access() -> None:
            eagle = Eagle.objects.select_related("location").get(pk=pk)
            _ = eagle.location

        load_and_access()
        assert unused.is_active() is False


class TestWarnUnusedDisabled(BaseRequestTest):
    """When EAGLE_ENABLED is falsy the decorator is a transparent passthrough."""

    @override_settings(EAGLE_ENABLED=False)
    def test_disabled_is_passthrough_no_warning(self, eagle_graph: EagleGraph):
        pk = eagle_graph.eagle.pk

        @warn_unused
        def load_unused() -> str:
            Eagle.objects.select_related("location").get(pk=pk)
            return "done"

        assert load_unused() == "done"

    @override_settings(EAGLE_ENABLED=False)
    def test_disabled_does_not_activate_collector(self, eagle_graph: EagleGraph):
        pk = eagle_graph.eagle.pk

        @warn_unused
        def load_unused() -> None:
            Eagle.objects.select_related("location").get(pk=pk)

        load_unused()
        assert unused.is_active() is False


class TestWarnUnusedExceptions:
    """Tracking always ends, so a failing call never leaks an active collector onto the thread."""

    def test_exception_propagates_and_no_leak(self):
        class Boom(Exception):
            pass

        @warn_unused
        def explode() -> None:
            raise Boom

        with pytest.raises(Boom):
            explode()
        assert unused.is_active() is False


class TestWarnUnusedMetadata:
    """The wrapper preserves the wrapped callable's identifying metadata."""

    def test_preserves_wrapper_metadata(self):
        @warn_unused
        def documented(x: int) -> int:
            """Return x unchanged."""
            return x

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "Return x unchanged."


class TestWarnUnusedPublicExport:
    """warn_unused is part of the public top-level API."""

    def test_public_export(self):
        assert eagle.warn_unused is warn_unused


class TestWarnUnusedAsyncNoDb:
    """The async branch wraps the awaited call without touching the database."""

    def test_async_disabled_passthrough(self):
        @warn_unused
        async def doubler(x: int) -> int:
            return x * 2

        with override_settings(EAGLE_ENABLED=False):
            assert asyncio.run(doubler(3)) == 6
        assert unused.is_active() is False

    def test_async_enabled_no_loads_returns_value(self):
        @warn_unused
        async def producer() -> int:
            return 7

        # Tracking begins and ends around the await; with no loads, nothing is warned.
        assert asyncio.run(producer()) == 7
        assert unused.is_active() is False
