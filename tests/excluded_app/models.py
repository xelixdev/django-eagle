from django.db import models

from test_project.models import Eagle


class Burrow(models.Model):
    eagle = models.OneToOneField(Eagle, models.CASCADE, related_name="burrow")
    depth = models.IntegerField(default=0)
