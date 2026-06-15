import functools
import inspect
from collections.abc import Callable
from typing import ParamSpec, TypeVar

from django.apps import apps
from django.db.models import Model

from eagle.logger import logger
from eagle.unused import mark_considered_internal

P = ParamSpec("P")
R = TypeVar("R")


def _normalize_model(model: type[Model] | str) -> str:
    """
    Resolve *model* to its Django label (``app_label.ModelName``) so it matches tracked keys.

    Tracking keys relations on ``model._meta.label`` to keep same-named models in different apps
    distinct, so the public escape hatches must resolve their argument to that same labelled form.

    Args:
        model: A Django model class, a label string (``app_label.ModelName``), or a bare class name.

    Returns:
        The model's ``_meta.label``. A class or labelled string resolves directly; a bare class name
        resolves via the app registry when exactly one model matches. The input is returned unchanged
        when it cannot be resolved (an unmatched or ambiguous bare name), which simply fails to match.
    """
    if isinstance(model, type):
        return model._meta.label

    name = str(model)

    if "." in name:
        try:
            return apps.get_model(name)._meta.label
        except (LookupError, ValueError):
            return name

    matches = [registered._meta.label for registered in apps.get_models() if registered.__name__ == name]
    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        logger.warning(
            "mark_considered/may_access got ambiguous model name %r matching %s; "
            "pass the model class or a labelled 'app_label.ModelName' string to disambiguate.",
            name,
            matches,
        )
    return name


def mark_considered(model: type[Model] | str, *cache_names: str) -> None:
    """
    Suppress warnings for *cache_names* on *model* in the current request.

    Args:
        model: The Django model class, a label string (``app_label.ModelName``), or a bare class name.
    """
    normalized = _normalize_model(model)
    logger.debug("Marking considered %s, %s.", normalized, cache_names)
    mark_considered_internal(normalized, *cache_names)


def may_access(model: type[Model] | str, *cache_names: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator that suppresses warnings for *cache_names* on *model* after the decorated function returns.

    Args:
        model: The Django model class, a label string (``app_label.ModelName``), or a bare class name.

    Returns:
        A decorator that wraps the function and calls mark_considered_internal after it executes.
    """
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
