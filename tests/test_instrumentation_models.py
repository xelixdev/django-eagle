from unittest.mock import Mock

from eagle.instrumentation import models
from test_project.models import Eagle


class TestMakeDescriptorEager:
    def test_missing_attribute_is_a_noop(self) -> None:
        models.make_descriptor_eager(object(), "does_not_exist")


class TestMakeRemoteFieldDescriptorEager:
    def test_uninstrumented_related_model_is_skipped(self, monkeypatch: object) -> None:
        calls: list[object] = []
        monkeypatch.setattr(models, "make_descriptor_eager", lambda *a: calls.append(a))

        models.make_remote_field_descriptor_eager(None, object, remote_field=Mock())

        assert calls == []

    def test_hidden_accessor_is_skipped(self, monkeypatch: object) -> None:
        calls: list[object] = []
        monkeypatch.setattr(models, "make_descriptor_eager", lambda *a: calls.append(a))
        remote_field = Mock(get_accessor_name=Mock(return_value=None))

        models.make_remote_field_descriptor_eager(None, Eagle, remote_field=remote_field)

        remote_field.get_accessor_name.assert_called_once()
        assert calls == []

    def test_visible_accessor_is_made_eager(self, monkeypatch: object) -> None:
        calls: list[object] = []
        monkeypatch.setattr(models, "make_descriptor_eager", lambda *a: calls.append(a))
        remote_field = Mock(get_accessor_name=Mock(return_value="visitors"))

        models.make_remote_field_descriptor_eager(None, Eagle, remote_field=remote_field)

        assert calls == [(Eagle, "visitors")]


class TestMakePrefetchCacheEager:
    def test_second_call_is_idempotent(self) -> None:
        models.make_prefetch_cache_eager(Eagle)
        first_descriptor = Eagle.__dict__["_prefetched_objects_cache"]

        models.make_prefetch_cache_eager(Eagle)

        assert Eagle.__dict__["_prefetched_objects_cache"] is first_descriptor


class TestMakeModelEagerHiddenRelation:
    def test_hidden_reverse_relation_is_skipped_without_error(self) -> None:
        mates_rel = next(rel for rel in Eagle._meta.related_objects if rel.get_accessor_name() is None)
        assert mates_rel.field.name == "mates"

        models.make_model_eager(Eagle)
