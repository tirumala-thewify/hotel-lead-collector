import re

from django.http import HttpResponse
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services.export import build_hotel_workbook
from .services.export.enrichment import prepare_hotels_for_export


MAX_EXPORT_ROWS = 1000


class ManagerContactSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    title = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    department = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    linkedin_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    role_group = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    confidence = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    business_email = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class BusinessEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class BusinessPhoneSerializer(serializers.Serializer):
    phone = serializers.CharField()
    normalized = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    type = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    source_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ExportHotelSerializer(serializers.Serializer):
    id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    place_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    distance_km = serializers.FloatField(required=False, allow_null=True)
    address = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    email = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    website = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    brand = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    stars = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    rating = serializers.FloatField(required=False, allow_null=True)
    review_count = serializers.IntegerField(required=False, allow_null=True)
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    source = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    enrichment_status = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    enrichment_sources = serializers.DictField(required=False)
    manager_contacts = ManagerContactSerializer(many=True, required=False)
    decision_makers = ManagerContactSerializer(many=True, required=False)
    business_emails = BusinessEmailSerializer(many=True, required=False)
    business_phones = BusinessPhoneSerializer(many=True, required=False)
    social_profiles = serializers.DictField(required=False)
    social_profile_sources = serializers.DictField(required=False)
    discovered_pages = serializers.DictField(required=False)
    website_confidence = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    category = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    maps_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    google_maps_url = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class SearchContextSerializer(serializers.Serializer):
    location = serializers.CharField(required=False, allow_blank=True, max_length=300)
    latitude = serializers.FloatField(required=True)
    longitude = serializers.FloatField(required=True)
    radius = serializers.FloatField(required=True, min_value=1, max_value=20000)
    provider = serializers.CharField(required=True, max_length=100)


class ExcelExportSerializer(serializers.Serializer):
    hotels = serializers.ListField(
        child=ExportHotelSerializer(),
        allow_empty=False,
        max_length=MAX_EXPORT_ROWS,
    )
    context = SearchContextSerializer(required=True)


class ExportPreparationSerializer(serializers.Serializer):
    hotels = serializers.ListField(
        child=ExportHotelSerializer(), allow_empty=False, max_length=MAX_EXPORT_ROWS,
    )


def _slug(value):
    slug = re.sub(r'[^a-z0-9]+', '-', (value or '').casefold()).strip('-')
    return slug[:80]


@api_view(['POST'])
def export_excel(request):
    serializer = ExcelExportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    workbook, exported_at = build_hotel_workbook(data['hotels'], data['context'])
    location_slug = _slug(data['context'].get('location'))
    date = exported_at.date().isoformat()
    filename = f"hotel-leads-{location_slug + '-' if location_slug else ''}{date}.xlsx"
    response = HttpResponse(
        workbook,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@api_view(['POST'])
def prepare_export(request):
    serializer = ExportPreparationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response({'hotels': prepare_hotels_for_export(serializer.validated_data['hotels'])})
