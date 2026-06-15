from django.db import models

from test_project.models import Location


class Eagle(models.Model):
    """
    An eagle in a second tracked app whose class name deliberately collides with ``test_project.Eagle``.

    Used by the cross-app collision regression test: it carries a ``location`` relation with the same
    cache name as ``test_project.Eagle.location`` so the two only stay distinct when keyed by label.
    """

    location = models.ForeignKey(Location, models.CASCADE, null=True, related_name="collision_visitors")
