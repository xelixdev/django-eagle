import functools
import inspect
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from django.db.models import Model

from eagle.unused import mark_considered_internal
from eagle.logger import logger


P = ParamSpec("P")
R = TypeVar("R")


def _normalize_model(model: type[Model] | str) -> str:
    if isinstance(model, type):
        return model.__name__
    return str(model)


def mark_considered(model: type[Model] | str, *cache_names: str) -> None:
    normalized = _normalize_model(model)
    logger.debug("Marking considered %s, %s.", normalized, cache_names)
    mark_considered_internal(normalized, *cache_names)


def may_access(model: type[Model] | str, *cache_names: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    model_name = _normalize_model(model)

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                result = await fn(*args, **kwargs)
                mark_considered_internal(model_name, *cache_names)
                return result

            return async_wrapper

        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            result = fn(*args, **kwargs)
            mark_considered_internal(model_name, *cache_names)
            return result

        return wrapper

    return decorator
