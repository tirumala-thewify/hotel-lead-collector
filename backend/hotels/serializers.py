from rest_framework import serializers


class NearbyHotelsQuerySerializer(serializers.Serializer):
    lat = serializers.FloatField(
        min_value=-90,
        max_value=90,
        required=True,
    )
    lng = serializers.FloatField(
        min_value=-180,
        max_value=180,
        required=True,
    )
    radius = serializers.FloatField(
        min_value=0,
        max_value=20_000,
        required=True,
    )

    def validate_radius(self, value):
        if value <= 0:
            raise serializers.ValidationError('Radius must be greater than 0.')
        return value


class HotelEnrichmentSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, max_length=300)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    brand = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    contact_website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    brand_website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    domain_hint = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    source = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    wikidata = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    wikipedia = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class BulkHotelEnrichmentSerializer(serializers.Serializer):
    hotels = HotelEnrichmentSerializer(many=True, allow_empty=False, max_length=10)


class ManagerEnrichmentSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, max_length=300)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    brand = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    location = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class BulkManagerHotelSerializer(serializers.Serializer):
    name = serializers.CharField(required=True, max_length=300)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    brand = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class BulkManagerEnrichmentSerializer(serializers.Serializer):
    hotels = BulkManagerHotelSerializer(many=True, allow_empty=False, max_length=10)
