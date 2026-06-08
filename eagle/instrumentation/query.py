from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from operator import attrgetter
from typing import Any

from django.db import models
from django.db.models import Prefetch
from django.db.models import query as dj_query
from django.db.models.options import Options
from django.db.models.query import ModelIterable, QuerySet
from django.db.models.query_utils import select_related_descend

from eagle import unused
from eagle.instrumentation.registry import is_instrumented

type Getter = tuple[str, Callable[[models.Model], Any], tuple[Getter, ...]]

cached_value_getter = attrgetter("get_cached_value")


def get_restricted_select_related_getters(lookups: Mapping[str, Mapping[str, Any]], opts: Options) -> Iterator[Getter]:
    for lookup, nested_lookups in lookups.items():
        field = opts.get_field(lookup)
        lookup_opts = field.related_model._meta
        yield (
            field.cache_name,
            cached_value_getter(field),
            tuple(get_restricted_select_related_getters(nested_lookups, lookup_opts)),
        )


def get_unrestricted_select_related_getters(opts: Options, max_depth: int, cur_depth: int = 1) -> Iterator[Getter]:
    if cur_depth > max_depth:
        return
    for field in opts.fields:
        if not select_related_descend(field, False, None, {}):
            continue
        related_model_meta = field.related_model._meta
        yield (
            field.cache_name,
            cached_value_getter(field),
            tuple(
                get_unrestricted_select_related_getters(
                    related_model_meta, max_depth=max_depth, cur_depth=cur_depth + 1
                )
            ),
        )


def walk_select_relateds(obj: models.Model, getters: tuple[Getter, ...]) -> Iterator[models.Model]:
    owner_instrumented = is_instrumented(obj.__class__)
    for cache_name, getter, nested_getters in getters:
        related_obj = getter(obj)
        if owner_instrumented:
            unused.mark_select_related(obj, cache_name)
        if related_obj is None:
            continue
        yield related_obj
        yield from walk_select_relateds(related_obj, nested_getters)


_EAGLE_LOCATION_ATTR = "_eagle_location"
_EAGLE_LOCATIONS_ATTR = "_eagle_locations"

_original_select_related = QuerySet.select_related
_original_prefetch_related = QuerySet.prefetch_related
_original_clone = QuerySet._clone


def propagate_prefetch_location(instances: list[models.Model], child_queryset: Any, cache_name: str | None) -> None:
    if cache_name is None or not instances or child_queryset is None:
        return
    if getattr(child_queryset, _EAGLE_LOCATION_ATTR, None) is not None:
        return
    location = unused.resolve_location(instances[0]._state, cache_name)
    if location is not None:
        child_queryset._eagle_location = location


def _record_locations(clone: QuerySet, names: Iterator[str]) -> None:
    location = unused.capture_location()
    locations = dict(getattr(clone, _EAGLE_LOCATIONS_ATTR, None) or {})
    for name in names:
        if name and name not in locations:
            locations[name] = location
    if locations:
        clone._eagle_locations = locations
    if getattr(clone, _EAGLE_LOCATION_ATTR, None) is None:
        clone._eagle_location = location


def _eager_select_related(self: QuerySet, *fields: Any) -> QuerySet:
    clone = _original_select_related(self, *fields)
    _record_locations(clone, (field for field in fields if isinstance(field, str)))
    return clone


def _eager_prefetch_related(self: QuerySet, *lookups: Any) -> QuerySet:
    clone = _original_prefetch_related(self, *lookups)
    names = (lookup.prefetch_to if isinstance(lookup, Prefetch) else lookup for lookup in lookups)
    _record_locations(clone, (name for name in names if isinstance(name, str)))
    return clone


def _eager_clone(self: QuerySet, *args: Any, **kwargs: Any) -> QuerySet:
    clone = _original_clone(self, *args, **kwargs)
    location = getattr(self, _EAGLE_LOCATION_ATTR, None)
    if location is not None:
        clone._eagle_location = location
    locations = getattr(self, _EAGLE_LOCATIONS_ATTR, None)
    if locations:
        clone._eagle_locations = locations
    return clone


class TrackedPrefetchList(list):
    def __init__(self, iterable: Any, instance: models.Model, cache_name: str) -> None:
        super().__init__(iterable)
        self._eagle_instance = instance
        self._eagle_cache_name = cache_name
        self._eagle_consumed = False

    def _eagle_consume(self) -> None:
        if not self._eagle_consumed:
            self._eagle_consumed = True
            unused.mark_consumed(self._eagle_instance, self._eagle_cache_name)

    def __iter__(self) -> Iterator[Any]:
        self._eagle_consume()
        return super().__iter__()

    def __len__(self) -> int:
        self._eagle_consume()
        return super().__len__()

    def __getitem__(self, item: Any) -> Any:
        self._eagle_consume()
        return super().__getitem__(item)

    def __contains__(self, item: Any) -> bool:
        self._eagle_consume()
        return super().__contains__(item)

    def __reversed__(self) -> Iterator[Any]:
        self._eagle_consume()
        return super().__reversed__()

    def __eq__(self, other: Any) -> bool:
        self._eagle_consume()
        return super().__eq__(other)

    __hash__ = None

    def __repr__(self) -> str:
        self._eagle_consume()
        return super().__repr__()

    def count(self, value: Any) -> int:
        self._eagle_consume()
        return super().count(value)

    def index(self, *args: Any) -> int:
        self._eagle_consume()
        return super().index(*args)


def _prefetcher_cache_name(prefetcher: Any) -> str | None:
    getter = getattr(prefetcher, "_prefetch_cache_name", None)
    if getter is None:
        return None
    return getter()


_original_prefetch_one_level = dj_query.prefetch_one_level


def _eager_prefetch_one_level(instances: list[models.Model], prefetcher: Any, lookup: Prefetch, level: int) -> Any:
    result = _original_prefetch_one_level(instances, prefetcher, lookup, level)
    if not unused.is_active() or not instances:
        return result
    to_attr, as_attr = lookup.get_current_to_attr(level)
    if not as_attr:
        return result
    cache_name = _prefetcher_cache_name(prefetcher)
    if cache_name is None:
        return result
    for obj in instances:
        if not getattr(obj._state, "warn_unused", False):
            continue
        value = getattr(obj, to_attr, None)
        if isinstance(value, TrackedPrefetchList):
            continue
        if isinstance(value, list):
            setattr(obj, to_attr, TrackedPrefetchList(value, obj, cache_name))
        else:
            unused.mark_consumed(obj, cache_name)
    return result


_original_model_iterable_iter = ModelIterable.__iter__


def _eager_model_iterable_iter(self: ModelIterable) -> Iterator[models.Model]:
    queryset = self.queryset
    if not unused.is_active() or not is_instrumented(queryset.model):
        yield from _original_model_iterable_iter(self)
        return

    location = getattr(queryset, _EAGLE_LOCATION_ATTR, None)
    locations = getattr(queryset, _EAGLE_LOCATIONS_ATTR, None)
    query = queryset.query
    select_related = query.select_related
    if select_related:
        opts = queryset.model._meta
        if isinstance(select_related, dict):
            getters = tuple(get_restricted_select_related_getters(select_related, opts))
        else:
            getters = tuple(get_unrestricted_select_related_getters(opts, max_depth=query.max_depth))
        for obj in _original_model_iterable_iter(self):
            unused.init_state(obj, location, locations)
            for related_obj in walk_select_relateds(obj, getters):
                unused.init_state(related_obj, location, locations)
            yield obj
    else:
        for obj in _original_model_iterable_iter(self):
            unused.init_state(obj, location, locations)
            yield obj


def install() -> None:
    if getattr(ModelIterable, "_eagle_patched", False):
        return
    ModelIterable.__iter__ = _eager_model_iterable_iter
    QuerySet.select_related = _eager_select_related
    QuerySet.prefetch_related = _eager_prefetch_related
    QuerySet._clone = _eager_clone
    dj_query.prefetch_one_level = _eager_prefetch_one_level
    ModelIterable._eagle_patched = True
