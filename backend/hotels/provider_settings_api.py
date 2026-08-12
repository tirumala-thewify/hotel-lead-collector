from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import ProviderSettings
from .provider_settings import (
    get_geoapify_api_key,
    get_google_api_key,
    get_apollo_api_key,
    get_zoominfo_api_key,
    get_provider_settings,
    public_provider_settings,
)


class ProviderSettingsUpdateSerializer(serializers.Serializer):
    hotel_provider = serializers.ChoiceField(
        choices=ProviderSettings.HOTEL_PROVIDER_CHOICES,
        required=False,
    )
    business_providers = serializers.ListField(
        child=serializers.ChoiceField(choices=ProviderSettings.HOTEL_PROVIDER_CHOICES),
        allow_empty=False,
        required=False,
        error_messages={'empty': 'Select at least one business data provider.'},
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
    people_providers = serializers.ListField(
        child=serializers.ChoiceField(choices=('apollo', 'zoominfo')),
        allow_empty=True, required=False,
    )
    zoominfo_api_key = serializers.CharField(
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
    people_providers = values.get('people_providers')
    if people_providers is not None:
        people_providers = list(dict.fromkeys(people_providers))
        errors = {}
        if 'apollo' in people_providers and not (
            values.get('apollo_api_key') or get_apollo_api_key(provider_settings)
        ):
            errors['people_providers'] = 'Apollo is not configured.'
        if 'zoominfo' in people_providers and not (
            values.get('zoominfo_api_key') or get_zoominfo_api_key(provider_settings)
        ):
            errors['people_providers'] = 'ZoomInfo is not configured.'
        if errors:
            raise serializers.ValidationError(errors)
        provider_settings.people_providers = people_providers
        provider_settings.apollo_enabled = 'apollo' in people_providers
    selected = values.get('business_providers')
    if selected is not None:
        selected = list(dict.fromkeys(selected))
        google_key = values.get('google_api_key') or get_google_api_key(provider_settings)
        geoapify_key = values.get('geoapify_api_key') or get_geoapify_api_key(provider_settings)
        configuration_errors = {}
        if ProviderSettings.GEOAPIFY in selected and not geoapify_key:
            configuration_errors['business_providers'] = 'Geoapify is not configured.'
        if ProviderSettings.GOOGLE in selected and not google_key:
            configuration_errors['business_providers'] = 'Google Places is not configured.'
        if configuration_errors:
            raise serializers.ValidationError(configuration_errors)
        provider_settings.business_providers = selected
        provider_settings.hotel_provider = selected[0]
    if 'hotel_provider' in values:
        provider_settings.hotel_provider = values['hotel_provider']
    if 'apollo_enabled' in values:
        provider_settings.apollo_enabled = values['apollo_enabled']
        if people_providers is None:
            current_people = list(provider_settings.people_providers or [])
            if values['apollo_enabled'] and 'apollo' not in current_people:
                current_people.append('apollo')
            if not values['apollo_enabled']:
                current_people = [item for item in current_people if item != 'apollo']
            provider_settings.people_providers = current_people
    if 'google_api_key' in values:
        provider_settings.set_google_api_key(values['google_api_key'])
    if values.get('geoapify_api_key'):
        provider_settings.set_geoapify_api_key(values['geoapify_api_key'])
    if 'apollo_api_key' in values:
        if values['apollo_api_key']:
            provider_settings.set_apollo_api_key(values['apollo_api_key'])
    if values.get('zoominfo_api_key'):
        provider_settings.set_zoominfo_api_key(values['zoominfo_api_key'])
    provider_settings.save()
    return Response(public_provider_settings(provider_settings), status=status.HTTP_200_OK)
