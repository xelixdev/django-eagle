from types import SimpleNamespace

import pytest
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from eagle import UnusedRelatedAccess, unused, warn_unused
from eagle.instrumentation import descriptors
from test_project.models import Aerie, Eagle, Sighting
from tests.factories import AerieFactory, EagleFactory


class TestEagerPrefetchMixinBase:
    def test_default_prefetch_cache_name_is_none(self) -> None:
        assert descriptors.EagerPrefetchMixin()._prefetch_cache_name() is None


class TestLegacyGetPrefetchQueryset:
    def test_delegates_to_super_and_returns_its_result(self) -> None:
        class _LegacyBase:
            def get_prefetch_queryset(self, instances: list, queryset: object = None) -> tuple:
                return ("child-queryset", queryset)

        class _LegacyManager(descriptors.EagerPrefetchMixin, _LegacyBase):
            def _prefetch_cache_name(self) -> str:
                return "legacy_cache"

        result = _LegacyManager().get_prefetch_queryset([])

        assert result == ("child-queryset", None)


@pytest.mark.django_db
class TestTrackingPrefetchCache:
    @pytest.fixture
    def eagle(self) -> Eagle:
        return EagleFactory()

    def test_getitem_marks_consumed_when_instance_is_tracked(self, eagle: Eagle) -> None:
        unused.begin_request()
        unused.init_state(eagle, location=None)
        unused.mark_prefetched([eagle], "previous_locations")
        cache = descriptors.TrackingPrefetchCache({"previous_locations": []}, _eagle_instance=eagle)

        assert cache["previous_locations"] == []

        unused.end_request()

    def test_getitem_skips_marking_when_instance_untracked(self) -> None:
        cache = descriptors.TrackingPrefetchCache({"key": "value"}, _eagle_instance=None)
        assert cache["key"] == "value"


@pytest.mark.django_db
class TestPrefetchCacheDescriptor:
    @pytest.fixture
    def eagle(self) -> Eagle:
        return EagleFactory()

    def test_class_level_access_returns_descriptor_itself(self) -> None:
        descriptor = Eagle.__dict__["_prefetched_objects_cache"]
        assert descriptor.__get__(None, Eagle) is descriptor

    def test_set_does_not_rewrap_existing_tracking_cache(self, eagle: Eagle) -> None:
        descriptor = Eagle.__dict__["_prefetched_objects_cache"]
        existing = descriptors.TrackingPrefetchCache({}, _eagle_instance=eagle)

        descriptor.__set__(eagle, existing)

        assert eagle.__dict__[descriptor._eagle_storage] is existing

    def test_delete_missing_cache_raises_attribute_error(self, eagle: Eagle) -> None:
        descriptor = Eagle.__dict__["_prefetched_objects_cache"]
        with pytest.raises(AttributeError):
            descriptor.__delete__(eagle)

    def test_delete_existing_cache_removes_it(self, eagle: Eagle) -> None:
        descriptor = Eagle.__dict__["_prefetched_objects_cache"]
        descriptor.__set__(eagle, {})

        descriptor.__delete__(eagle)

        assert descriptor._eagle_storage not in eagle.__dict__


class TestCreateEagerRelatedManagerCacheNameFallback:
    def test_falls_back_to_related_query_name_without_prefetch_cache_name(self) -> None:
        class _StubRelatedManager:
            field = SimpleNamespace(related_query_name=lambda: "stub_query_name")

        manager_cls = descriptors.create_eager_related_manager(_StubRelatedManager)

        assert manager_cls()._prefetch_cache_name() == "stub_query_name"


@pytest.mark.django_db
class TestForwardOneToOnePrefetch:
    @pytest.fixture
    def aerie(self) -> Aerie:
        return AerieFactory(eagle=EagleFactory())

    def test_forward_o2o_prefetch_unused_warns(self, aerie: Aerie) -> None:
        with pytest.raises(UnusedRelatedAccess) as exc_info, warn_unused():
            Aerie.objects.prefetch_related("eagle").get(pk=aerie.pk)
        assert 'prefetch_related("eagle")' in str(exc_info.value)

    def test_forward_o2o_prefetch_accessed_no_warning(self, aerie: Aerie) -> None:
        with warn_unused():
            fetched = Aerie.objects.prefetch_related("eagle").get(pk=aerie.pk)
            assert fetched.eagle == aerie.eagle


class TestMakeContenttypesEagerIdempotent:
    def test_second_call_does_not_duplicate_registration(self) -> None:
        before = len(descriptors._eager_mixins)
        descriptors.make_contenttypes_eager()
        assert len(descriptors._eager_mixins) == before


class TestLegacyGenericForeignKeyGetPrefetchQueryset:
    def test_delegates_to_super_and_returns_its_result(self) -> None:
        gfk_mixin = next(mixin for stock_class, mixin in descriptors._eager_mixins if stock_class is GenericForeignKey)

        class _LegacyBase:
            cache_name = "content_object"

            def get_prefetch_queryset(self, instances: list, queryset: object = None) -> tuple:
                return ("child-queryset", queryset)

        class _LegacyGenericForeignKey(gfk_mixin, _LegacyBase):
            pass

        result = _LegacyGenericForeignKey().get_prefetch_queryset([])

        assert result == ("child-queryset", None)


@pytest.mark.django_db
class TestGenericForeignKeyTracking:
    @pytest.fixture
    def sighting(self) -> Sighting:
        eagle = EagleFactory()
        return Sighting.objects.create(content_type=ContentType.objects.get_for_model(Eagle), object_id=eagle.pk)

    def test_prefetched_generic_foreign_key_unused_warns(self, sighting: Sighting) -> None:
        with pytest.raises(UnusedRelatedAccess) as exc_info, warn_unused():
            Sighting.objects.prefetch_related("content_object").get(pk=sighting.pk)
        assert 'prefetch_related("content_object")' in str(exc_info.value)

    def test_prefetched_generic_foreign_key_accessed_no_warning(self, sighting: Sighting) -> None:
        with warn_unused():
            fetched = Sighting.objects.prefetch_related("content_object").get(pk=sighting.pk)
            assert fetched.content_object is not None
