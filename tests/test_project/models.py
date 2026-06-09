from django.db import models


class Climate(models.Model):
    temperature = models.IntegerField()


class Location(models.Model):
    latitude = models.FloatField()
    longitude = models.FloatField()
    climates = models.ManyToManyField(Climate, blank=True, related_name="locations")


class Eagle(models.Model):
    height = models.PositiveIntegerField()
    weight = models.PositiveIntegerField()
    location = models.ForeignKey(Location, models.CASCADE, null=True, related_name="visitors")
    previous_locations = models.ManyToManyField(Location, related_name="previous_visitors")

    def __repr__(self):
        return f"<Eagle {self.id} {self.height} {self.weight}>"


class Eaglet(models.Model):
    eagle = models.OneToOneField(Eagle, models.CASCADE, null=True, related_name="eaglet")
