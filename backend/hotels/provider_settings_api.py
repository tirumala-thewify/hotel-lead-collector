from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ProviderSettings
from .provider_settings import get_provider_settings, public_provider_settings


class ProviderSettingsUpdateSerializer(serializers.Serializer):
    hotel_provider = serializers.ChoiceField(
        choices=ProviderSettings.HOTEL_PROVIDER_CHOICES,
        required=False,
    )
    google_api_key = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, write_only=True
    )
    geoapify_api_key = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, write_only=True
    )
    apollo_enabled = serializers.BooleanField(required=False)
    apollo_api_key = serializers.CharField(
        required=False, allow_blank=True, trim_whitespace=False, write_only=True
    )


@api_view(['GET', 'PUT'])
def provider_settings_view(request):
    provider_settings = get_provider_settings()
    if request.method == 'GET':
        return Response(public_provider_settings(provider_settings))

    serializer = ProviderSettingsUpdateSerializer(data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    if 'hotel_provider' in values:
        provider_settings.hotel_provider = values['hotel_provider']
    if 'apollo_enabled' in values:
        provider_settings.apollo_enabled = values['apollo_enabled']
    if 'google_api_key' in values:
        provider_settings.set_google_api_key(values['google_api_key'])
    if values.get('geoapify_api_key'):
        provider_settings.set_geoapify_api_key(values['geoapify_api_key'])
    if 'apollo_api_key' in values:
        provider_settings.set_apollo_api_key(values['apollo_api_key'])
    provider_settings.save()
    return Response(public_provider_settings(provider_settings), status=status.HTTP_200_OK)
