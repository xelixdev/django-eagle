import pytest

from collision_app.models import Eagle as CollisionEagle
from eagle import UnusedRelatedAccess, mark_considered, unused
from test_project.models import Eagle
from tests.base import MayAccessHelperTestBase
from tests.factories import CollisionEagleFactory, EagleFactory


class TestCrossAppCollision(MayAccessHelperTestBase):
    """
    Same-named models in different apps must not share loaded/consumed keys.

    ``test_project.Eagle`` and ``collision_app.Eagle`` have the same class name and a ``location``
    relation with the same cache name. Keys are built from ``model._meta.label`` so a consumed
    relation on one app's model cannot mask an unused one on the other's.
    """

    def test_consumed_relation_does_not_mask_unused_on_same_named_model(self):
        # collision_app.Eagle.location is loaded and accessed -> consumed.
        consumed = CollisionEagleFactory()
        loaded_collision = CollisionEagle.objects.select_related("location").get(pk=consumed.pk)
        assert loaded_collision.location is not None

        # test_project.Eagle.location is loaded but never accessed -> unused.
        unused_eagle = EagleFactory()
        Eagle.objects.select_related("location").filter(pk=unused_eagle.pk).first()

        # When keyed by bare class name both relations collided on ("Eagle", "location"), so the
        # consumed collision_app load masked this unused test_project load and no warning fired.
        with pytest.raises(UnusedRelatedAccess) as exc_info:
            unused.end_request()
        assert 'select_related("location")' in str(exc_info.value)

    def test_consumed_relation_on_test_project_model_does_not_mask_collision_app(self):
        # Reverse roles: test_project.Eagle.location is consumed, collision_app.Eagle.location is unused.
        consumed = EagleFactory()
        loaded_eagle = Eagle.objects.select_related("location").get(pk=consumed.pk)
        assert loaded_eagle.location is not None

        unused_collision = CollisionEagleFactory()
        CollisionEagle.objects.select_related("location").filter(pk=unused_collision.pk).first()

        with pytest.raises(UnusedRelatedAccess) as exc_info:
            unused.end_request()
        assert 'select_related("location")' in str(exc_info.value)

    def test_consuming_both_same_named_models_emits_no_warning(self):
        # Both apps' relations are loaded and accessed; ending the request must stay silent.
        from_test_project = EagleFactory()
        loaded_eagle = Eagle.objects.select_related("location").get(pk=from_test_project.pk)
        assert loaded_eagle.location is not None

        from_collision = CollisionEagleFactory()
        loaded_collision = CollisionEagle.objects.select_related("location").get(pk=from_collision.pk)
        assert loaded_collision.location is not None

        # A surviving unused relation would raise here (warnings are errors); silence means success.
        unused.end_request()

    def test_mark_considered_labelled_form_suppresses_matching_model(self):
        eagle = EagleFactory()
        Eagle.objects.select_related("location").filter(pk=eagle.pk).first()

        # The labelled "app_label.ModelName" form resolves to the same key the load was recorded under.
        mark_considered("test_project.Eagle", "location")

        unused.end_request()

    def test_mark_considered_labelled_form_does_not_suppress_other_app(self):
        eagle = EagleFactory()
        Eagle.objects.select_related("location").filter(pk=eagle.pk).first()

        # Marking the same-named model in a different app must not suppress this load.
        mark_considered("collision_app.Eagle", "location")

        with pytest.raises(UnusedRelatedAccess) as exc_info:
            unused.end_request()
        assert 'select_related("location")' in str(exc_info.value)
