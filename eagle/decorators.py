import functools
import inspect
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from eagle.config import is_enabled
from eagle.unused import begin_request, end_request

P = ParamSpec("P")
R = TypeVar("R")


def warn_unused(fn: Callable[P, R]) -> Callable[P, R]:
    """
    Scope Eagle's unused-relation tracking to a single call of *fn*.

    Begins tracking before *fn* runs and ends it afterwards -- exactly as
    ``EagleWarnUnusedMiddleware`` does for a request/response cycle -- so any
    relation eager-loaded with ``select_related``/``prefetch_related`` inside
    *fn* but never accessed surfaces as an ``UnusedRelatedAccess`` warning when
    *fn* returns. Use it to get request-style detection in code that runs
    outside the request cycle: management commands, Celery tasks, or any plain
    function or method.

    Tracking always ends even if *fn* raises, so a failing call never leaks an
    active collector into later work on the same thread. When ``EAGLE_ENABLED``
    is falsy the wrapper is a transparent passthrough. Works for both
    synchronous and asynchronous callables and preserves wrapper metadata
    (``__name__``, ``__doc__``).

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
