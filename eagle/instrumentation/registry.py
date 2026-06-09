from collections.abc import Iterable

from django.db.models import Model

_instrumented: set[type[Model]] = set()


def register_tracked_models(models: Iterable[type[Model]]) -> None:
    """
    Record models as subject to Eagle tracking.

    Args:
        models: Django model classes to register; descriptor patches and ORM hooks
            use this set to decide whether to record access on a given model.
    """
    _instrumented.update(models)


def is_instrumented(model: type[Model]) -> bool:
    """
    Return True if *model* was registered for Eagle tracking.

    Args:
        model: The Django model class to look up.

    Returns:
        True if the model has been registered via register_tracked_models.
    """
    return model in _instrumented


def clear() -> None:
    """Remove all registered models; used in tests to reset state between runs."""
    _instrumented.clear()
