from rest_framework import serializers

from test_project.models import Eagle


class EagleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    related = serializers.SerializerMethodField()

    def get_related(self, eagle: Eagle) -> dict:
        access = self.context.get("access", ())
        related: dict = {}

        if "location" in access:
            related["location"] = eagle.location.latitude if eagle.location_id else None

        if "previous_locations" in access:
            related["previous_locations"] = [loc.id for loc in eagle.previous_locations.all()]

        if "previous_locations__climates" in access:
            related["previous_locations__climates"] = [
                [climate.id for climate in loc.climates.all()] for loc in eagle.previous_locations.all()
            ]

        if "previous_locations__climates__locations" in access:
            related["previous_locations__climates__locations"] = [
                [[home.id for home in climate.locations.all()] for climate in loc.climates.all()]
                for loc in eagle.previous_locations.all()
            ]

        if "previous_locations_raw" in access:
            cache = eagle._prefetched_objects_cache
            related["previous_locations_raw"] = [loc.id for loc in cache["previous_locations"]]

        if "eaglet" in access:
            related["eaglet"] = eagle.eaglet.id

        if "eaglet__eagle" in access:
            related["eaglet__eagle"] = eagle.eaglet.eagle.id

        if "burrow" in access:
            related["burrow"] = eagle.burrow.depth

        to_attr = self.context.get("to_attr")
        if to_attr and "to_attr" in access:
            related["to_attr"] = [obj.id for obj in getattr(eagle, to_attr)]

        return related
