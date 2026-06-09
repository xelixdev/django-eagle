from collections.abc import Iterable

from django.db.models import Model

_instrumented: set[type[Model]] = set()


def register(models: Iterable[type[Model]]) -> None:
    _instrumented.update(models)


def is_instrumented(model: type[Model]) -> bool:
    return model in _instrumented


def clear() -> None:
    _instrumented.clear()
