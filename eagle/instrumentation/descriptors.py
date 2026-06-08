from typing import Any

from django.db.models import Model
from django.db.models.fields.related import (
    ForwardManyToOneDescriptor,
    ForwardOneToOneDescriptor,
    ManyToManyDescriptor,
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
)
from django.db.models.manager import Manager
from django.utils.functional import cached_property

from eagle import unused
from eagle.instrumentation.query import propagate_prefetch_location


class EagerPrefetchMixin:
    def _prefetch_cache_name(self) -> str | None:
        return None

    def get_prefetch_queryset(self, instances: list[Model], queryset: Any = None) -> Any:
        cache_name = self._prefetch_cache_name()
        unused.mark_prefetched(instances, cache_name)
        result = super().get_prefetch_queryset(instances, queryset)
        propagate_prefetch_location(instances, result[0], cache_name)
        return result

    def get_prefetch_querysets(self, instances: list[Model], querysets: Any = None) -> Any:
        cache_name = self._prefetch_cache_name()
        unused.mark_prefetched(instances, cache_name)
        result = super().get_prefetch_querysets(instances, querysets)
        propagate_prefetch_location(instances, result[0], cache_name)
        return result


class TrackingPrefetchCache(dict):
    def __init__(self, *args: Any, _eagle_instance: Model | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._eagle_instance = _eagle_instance

    def __getitem__(self, key: Any) -> Any:
        value = super().__getitem__(key)
        instance = self._eagle_instance
        if instance is not None and getattr(instance._state, "warn_unused", False):
            unused.mark_consumed_prefetched(instance, key)
        return value


class PrefetchCacheDescriptor:
    _eagle_storage = "_eagle_prefetched_objects_cache"

    def __get__(self, instance: Model | None, cls: type[Model] | None = None) -> Any:
        if instance is None:
            return self
        try:
            return instance.__dict__[self._eagle_storage]
        except KeyError:
            e = "_prefetched_objects_cache"
            raise AttributeError(e) from None

    def __set__(self, instance: Model, value: Any) -> None:
        if not isinstance(value, TrackingPrefetchCache):
            value = TrackingPrefetchCache(value, _eagle_instance=instance)
        instance.__dict__[self._eagle_storage] = value

    def __delete__(self, instance: Model) -> None:
        try:
            del instance.__dict__[self._eagle_storage]
        except KeyError:
            e = "_prefetched_objects_cache"
            raise AttributeError(e) from None


def create_eager_related_manager(related_manager_cls: type[Manager]) -> type[Manager]:
    class EagerRelatedManager(EagerPrefetchMixin, related_manager_cls):
        def _prefetch_cache_name(self) -> str | None:
            try:
                return self.prefetch_cache_name
            except AttributeError:
                return self.field.related_query_name()

        def get_queryset(self) -> Any:
            if getattr(self.instance._state, "warn_unused", False):
                cache_name = self._prefetch_cache_name()
                try:
                    cached = self.instance._prefetched_objects_cache[cache_name]
                except (AttributeError, KeyError):
                    pass
                else:
                    unused.mark_consumed_prefetched(self.instance, cache_name)
                    return cached
            return super().get_queryset()

    return EagerRelatedManager


class EagerForwardManyToOneMixin:
    def __get__(self, instance: Model | None, cls: type[Model] | None = None) -> Any:
        if instance is not None and getattr(instance._state, "warn_unused", False) and self.field.is_cached(instance):
            unused.mark_consumed(instance, self.field.cache_name)
        return super().__get__(instance, cls)


class EagerForwardOneToOneMixin(EagerPrefetchMixin):
    def _prefetch_cache_name(self) -> str | None:
        return self.field.cache_name

    def __get__(self, instance: Model | None, cls: type[Model] | None = None) -> Any:
        if instance is not None and getattr(instance._state, "warn_unused", False) and self.field.is_cached(instance):
            unused.mark_consumed(instance, self.field.cache_name)
        return super().__get__(instance, cls)


class EagerReverseOneToOneMixin(EagerPrefetchMixin):
    def _prefetch_cache_name(self) -> str | None:
        return self.related.cache_name

    def __get__(self, instance: Model | None, cls: type[Model] | None = None) -> Any:
        if instance is not None and getattr(instance._state, "warn_unused", False) and self.related.is_cached(instance):
            unused.mark_consumed(instance, self.related.cache_name)
        return super().__get__(instance, cls)


class EagerRelatedManagerMixin:
    @cached_property
    def related_manager_cls(self) -> type[Manager]:
        return create_eager_related_manager(super().related_manager_cls)


_eager_mixins: list[tuple[type, type]] = [
    (ForwardOneToOneDescriptor, EagerForwardOneToOneMixin),
    (ForwardManyToOneDescriptor, EagerForwardManyToOneMixin),
    (ReverseOneToOneDescriptor, EagerReverseOneToOneMixin),
    (ManyToManyDescriptor, EagerRelatedManagerMixin),
    (ReverseManyToOneDescriptor, EagerRelatedManagerMixin),
]

_composed_cache: dict[type, type] = {}


def _find_mixin(descriptor: object) -> type | None:
    for stock_class, mixin in _eager_mixins:
        if isinstance(descriptor, stock_class):
            return mixin
    return None


def make_descriptor_eager_inplace(descriptor: object) -> None:
    current = descriptor.__class__
    if getattr(current, "_eagle_eager", False):
        return
    composed = _composed_cache.get(current)
    if composed is None:
        mixin = _find_mixin(descriptor)
        if mixin is None:
            return
        composed = type(f"Eager{current.__name__}", (mixin, current), {"_eagle_eager": True})
        _composed_cache[current] = composed
    descriptor.__class__ = composed


def make_contenttypes_eager() -> None:
    from django.contrib.contenttypes.fields import (
        GenericForeignKey,
        ReverseGenericManyToOneDescriptor,
    )

    if any(stock_class is GenericForeignKey for stock_class, _ in _eager_mixins):
        return

    class EagerGenericForeignKeyMixin:
        def __get__(self, instance: Model | None, cls: type[Model] | None = None) -> Any:
            if instance is not None and getattr(instance._state, "warn_unused", False) and self.is_cached(instance):
                unused.mark_consumed(instance, self.cache_name)
            return super().__get__(instance, cls=cls)

        def get_prefetch_queryset(self, instances: list[Model], queryset: Any = None) -> Any:
            unused.mark_prefetched(instances, self.cache_name)
            result = super().get_prefetch_queryset(instances, queryset)
            propagate_prefetch_location(instances, result[0], self.cache_name)
            return result

        def get_prefetch_querysets(self, instances: list[Model], querysets: Any = None) -> Any:
            unused.mark_prefetched(instances, self.cache_name)
            result = super().get_prefetch_querysets(instances, querysets)
            propagate_prefetch_location(instances, result[0], self.cache_name)
            return result

    _eager_mixins.insert(0, (ReverseGenericManyToOneDescriptor, EagerRelatedManagerMixin))
    _eager_mixins.insert(0, (GenericForeignKey, EagerGenericForeignKeyMixin))
