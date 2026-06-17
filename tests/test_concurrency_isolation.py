import asyncio
import threading
import warnings
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from django.db import connections

from eagle import UnusedRelatedAccess, warn_unused
from test_project.models import Eagle
from tests.factories import EagleFactory


def _run_async_and_capture(make_coro: Callable[[], Coroutine[Any, Any, None]]) -> list[warnings.WarningMessage]:
    """
    Run an async orchestrator and return any UnusedRelatedAccess warnings it emitted.

    Recording (rather than letting the configured ``error`` filter raise) lets a single
    test observe how warnings land across two interleaved requests instead of failing at
    the first one.

    Args:
        make_coro: Zero-arg factory returning the coroutine to drive with ``asyncio.run``.

    Returns:
        The captured ``UnusedRelatedAccess`` warning messages, in emission order.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        asyncio.run(make_coro())
    return [w for w in caught if issubclass(w.category, UnusedRelatedAccess)]


def _close_context_connection() -> None:
    """
    Force-close the database connection bound to the current thread or asyncio task.

    Each interleaved request below runs in its own thread or task, and Django's
    context-aware registry hands each one a separate connection to the shared in-memory
    test database. ``connections.close_all()`` cannot reclaim those: the SQLite backend
    makes ``close()`` a no-op for in-memory databases (closing the last handle would
    destroy the data), so the extra connections would otherwise be finalized while still
    open and raise ``ResourceWarning``. Closing the driver connection directly is safe
    because the test's own connection keeps the shared in-memory database alive.
    """
    connection = connections["default"]
    if connection.connection is not None:
        connection.connection.close()
        connection.connection = None


@pytest.mark.django_db(transaction=True)
class TestAsyncRequestIsolation:
    """
    Concurrent ASGI-style requests sharing one event-loop thread must not contaminate each other.

    Each request is its own asyncio task, so each runs in a copied context; the ContextVar-backed
    collector keeps their tracking separate even when one request begins while another is suspended
    at an ``await``. A thread-local collector would share state across the tasks and fail these.

    ``transaction=True`` commits the fixture row so each task's own (context-local) database
    connection can read it without contending on the test's transaction lock.
    """

    @pytest.fixture(autouse=True)
    def _allow_sync_orm_in_async(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Permit synchronous ORM calls inside the event loop for the duration of the test.

        The queries here run cooperatively on the loop thread (never truly in parallel), so
        Django's async-safety guard would be a false alarm.
        """
        monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

    def test_suspended_request_keeps_its_own_consumption(self) -> None:
        """A request that loaded and accessed its relation must not warn when another request interleaves."""
        pk = EagleFactory().pk

        async def orchestrate() -> None:
            a_consumed = asyncio.Event()
            b_loaded = asyncio.Event()
            a_finished = asyncio.Event()

            async def request_a() -> None:
                try:
                    with warn_unused():
                        eagle = Eagle.objects.select_related("location").get(pk=pk)
                        _ = eagle.location  # A reads its relation, so A alone must never warn.
                        a_consumed.set()
                        # Stay open (suspended) until B has loaded but not yet consumed.
                        await b_loaded.wait()
                    # Exiting here ends A's request while B's relation is still unconsumed.
                    a_finished.set()
                finally:
                    _close_context_connection()

            async def request_b() -> None:
                try:
                    await a_consumed.wait()  # Begin only once A is mid-flight.
                    with warn_unused():
                        eagle = Eagle.objects.select_related("location").get(pk=pk)
                        b_loaded.set()  # Loaded but deliberately not yet accessed.
                        await a_finished.wait()  # Let A end first, with B's load outstanding.
                        _ = eagle.location  # B reads its relation after A has ended.
                finally:
                    _close_context_connection()

            await asyncio.gather(request_a(), request_b())

        # Both requests read their relation, so the correct outcome is zero warnings. A shared
        # collector would let B's unconsumed load surface as a false positive against A.
        assert _run_async_and_capture(orchestrate) == []

    def test_suspended_unused_load_still_warns(self) -> None:
        """A request's genuinely unused load must still warn even though another request runs and resets first."""
        pk = EagleFactory().pk

        async def orchestrate() -> None:
            b_loaded = asyncio.Event()
            a_finished = asyncio.Event()

            async def request_a() -> None:
                try:
                    await b_loaded.wait()  # Begin only after B has an outstanding unused load.
                    with warn_unused():
                        eagle = Eagle.objects.select_related("location").get(pk=pk)
                        _ = eagle.location  # A reads its relation, so A must not warn.
                    a_finished.set()
                finally:
                    _close_context_connection()

            async def request_b() -> None:
                try:
                    with warn_unused():
                        eagle = Eagle.objects.select_related("location").get(pk=pk)
                        _ = eagle  # Loaded but the relation is never accessed: B must warn.
                        b_loaded.set()
                        await a_finished.wait()  # A runs (and resets a shared collector) before B ends.
                    # Exiting here ends B's request; its unused load must still be reported.
                finally:
                    _close_context_connection()

            await asyncio.gather(request_a(), request_b())

        captured = _run_async_and_capture(orchestrate)
        assert len(captured) == 1
        assert 'select_related("location")' in str(captured[0].message)


@pytest.mark.django_db(transaction=True)
class TestThreadRequestIsolation:
    """
    Per-thread isolation still holds under the ContextVar collector, so the sync request path is unaffected.

    Each thread runs with its own fresh context, so two overlapping tracking scopes on different
    threads keep separate loaded/consumed sets -- exactly as the old thread-local collector did.
    """

    def test_overlapping_threads_track_independently(self) -> None:
        """Two threads with overlapping scopes warn only for the thread whose load went unused."""
        pk = EagleFactory().pk

        b_loaded = threading.Event()
        a_finished = threading.Event()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")

            def request_a() -> None:
                try:
                    b_loaded.wait()  # Start only once B has an outstanding unused load.
                    with warn_unused():
                        loaded = Eagle.objects.select_related("location").get(pk=pk)
                        _ = loaded.location  # Accessed, so thread A must not warn.
                    a_finished.set()
                finally:
                    _close_context_connection()

            def request_b() -> None:
                try:
                    with warn_unused():
                        loaded = Eagle.objects.select_related("location").get(pk=pk)
                        _ = loaded  # Loaded but never accessed: thread B must warn.
                        b_loaded.set()
                        a_finished.wait()  # A's scope overlaps B's before B ends.
                finally:
                    _close_context_connection()

            thread_a = threading.Thread(target=request_a)
            thread_b = threading.Thread(target=request_b)
            thread_a.start()
            thread_b.start()
            thread_a.join()
            thread_b.join()

        unused_warnings = [w for w in caught if issubclass(w.category, UnusedRelatedAccess)]
        assert len(unused_warnings) == 1
        assert 'select_related("location")' in str(unused_warnings[0].message)
