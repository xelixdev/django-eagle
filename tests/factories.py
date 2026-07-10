from typing import Any

import factory

from collision_app.models import Eagle as CollisionEagle
from excluded_app.models import Burrow
from test_project.models import Aerie, Climate, Eagle, Eaglet, Location, Sighting


class ClimateFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Climate

    temperature = 20


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location
        skip_postgeneration_save = True

    latitude = 51.0
    longitude = 1.0

    @factory.post_generation
    def climates(self, create: bool, extracted: list[Climate], **kwargs: Any):
        if not create or not extracted:
            return
        self.climates.add(*extracted)


class EagleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Eagle

    height = 1
    weight = 100
    location = factory.SubFactory(LocationFactory)


class EagletFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Eaglet

    eagle = factory.SubFactory(EagleFactory)


class AerieFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Aerie

    eagle = factory.SubFactory(EagleFactory)


class BurrowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Burrow

    eagle = factory.SubFactory(EagleFactory)
    depth = 3


class SightingFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Sighting

    content_object = factory.SubFactory(EagleFactory)


class CollisionEagleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CollisionEagle

    location = factory.SubFactory(LocationFactory)
