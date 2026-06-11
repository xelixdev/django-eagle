import functools
import inspect
from collections.abc import Callable
from types import TracebackType
from typing import ParamSpec, TypeVar, overload

from eagle.config import is_enabled
from eagle.unused import begin_request, end_request

P = ParamSpec("P")
R = TypeVar("R")


def _wrap(fn: Callable[P, R]) -> Callable[P, R]:
    """
    Wrap *fn* so Eagle's unused-relation tracking is scoped to each call.

    Begins tracking before *fn* runs and ends it in a ``finally`` so tracking
    always ends even if *fn* raises. When ``EAGLE_ENABLED`` is falsy the wrapper
    is a transparent passthrough. Coroutine functions are wrapped so tracking
    spans the awaited call rather than ending the moment the coroutine is
    created.

    Args:
        fn: The synchronous or asynchronous callable to scope tracking around.

    Returns:
        A wrapped callable that emits unused-relation warnings after each call.
    """
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not is_enabled():
                return await fn(*args, **kwargs)
            begin_request()
            try:
                return await fn(*args, **kwargs)
            finally:
                end_request()

        return async_wrapper

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if not is_enabled():
            return fn(*args, **kwargs)
        begin_request()
        try:
            return fn(*args, **kwargs)
        finally:
            end_request()

    return wrapper


class _WarnUnusedScope:
    """
    Scope Eagle's unused-relation tracking to a ``with`` block or a call.

    Returned by ``warn_unused()`` (no arguments) so the same name can be used as
    a context manager (``with warn_unused(): ...``) or as a parenthesised
    decorator (``@warn_unused()``). When ``EAGLE_ENABLED`` is falsy entering the
    scope is a no-op, so nothing is tracked and nothing is warned.
    """

    def __init__(self) -> None:
        # Whether ``__enter__`` actually began tracking, so ``__exit__`` only
        # ends a scope it started (and stays a no-op when Eagle is disabled).
        self._active = False

    # PYI034 suggests ``Self``, unavailable from ``typing`` on the py310 target.
    def __enter__(self) -> "_WarnUnusedScope":  # noqa: PYI034
        """
        Begin tracking for the block, unless Eagle is disabled.

        Returns:
            This scope instance.
        """
        self._active = is_enabled()
        if self._active:
            begin_request()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        """
        End tracking, emitting warnings for relations loaded but never accessed.

        Tracking ends even when the block raises, so a failing block never leaks
        an active collector into later work on the same thread.

        Args:
            exc_type: Exception type raised in the block, if any.
            exc: Exception instance raised in the block, if any.
            tb: Traceback of the exception raised in the block, if any.

        Returns:
            False, so any exception raised inside the block propagates.
        """
        if self._active:
            self._active = False
            end_request()
        return False

    def __call__(self, fn: Callable[P, R]) -> Callable[P, R]:
        """
        Use the scope as a decorator, scoping tracking to each call of *fn*.

        Args:
            fn: The synchronous or asynchronous callable to scope tracking around.

        Returns:
            A wrapped callable that emits unused-relation warnings after each call.
        """
        return _wrap(fn)


@overload
def warn_unused(fn: Callable[P, R]) -> Callable[P, R]: ...


@overload
def warn_unused(fn: None = ...) -> _WarnUnusedScope: ...


def warn_unused(fn: Callable[P, R] | None = None) -> Callable[P, R] | _WarnUnusedScope:
    """
    Scope Eagle's unused-relation tracking to a single call or ``with`` block.

    Begins tracking before the scoped code runs and ends it afterwards -- exactly
    as ``EagleWarnUnusedMiddleware`` does for a request/response cycle -- so any
    relation eager-loaded with ``select_related``/``prefetch_related`` inside the
    scope but never accessed surfaces as an ``UnusedRelatedAccess`` warning when
    the scope ends. Use it to get request-style detection in code that runs
    outside the request cycle: management commands, Celery tasks, or any plain
    function, method, or block.

    Supports three forms::

        @warn_unused
        def task(): ...

        @warn_unused()
        def task(): ...

        with warn_unused():
            ...

    Tracking always ends even if the scoped code raises, so a failure never
    leaks an active collector into later work on the same thread. When
    ``EAGLE_ENABLED`` is falsy the scope is a transparent passthrough. The
    decorator forms work for both synchronous and asynchronous callables and
    preserve wrapper metadata (``__name__``, ``__doc__``).

    Args:
        fn: The callable to decorate when used as a bare ``@warn_unused``. Omit
            it (passing nothing) to get a context manager / parenthesised
            decorator instead.

    Returns:
        The wrapped callable when *fn* is given, otherwise a scope usable as a
        context manager or decorator.
    """
    if fn is None:
        return _WarnUnusedScope()
    return _wrap(fn)
