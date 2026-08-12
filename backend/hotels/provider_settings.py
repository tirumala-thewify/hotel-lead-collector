from django.conf import settings

from .models import ProviderSettings


def get_provider_settings():
    return ProviderSettings.load()


def get_google_api_key(provider_settings=None):
    provider_settings = provider_settings or get_provider_settings()
    return provider_settings.get_google_api_key() or settings.GOOGLE_MAPS_API_KEY


def get_geoapify_api_key(provider_settings=None):
    provider_settings = provider_settings or get_provider_settings()
    return provider_settings.get_geoapify_api_key() or settings.GEOAPIFY_API_KEY


def get_apollo_api_key(provider_settings=None):
    provider_settings = provider_settings or get_provider_settings()
    return provider_settings.get_apollo_api_key() or settings.APOLLO_API_KEY


def get_business_providers(provider_settings=None):
    provider_settings = provider_settings or get_provider_settings()
    selected = provider_settings.business_providers
    if not isinstance(selected, list) or not selected:
        selected = [provider_settings.hotel_provider or ProviderSettings.OPENSTREETMAP]
    valid = {choice[0] for choice in ProviderSettings.HOTEL_PROVIDER_CHOICES}
    return list(dict.fromkeys(provider for provider in selected if provider in valid))


def public_provider_settings(provider_settings=None):
    provider_settings = provider_settings or get_provider_settings()
    return {
        'hotel_provider': provider_settings.hotel_provider,
        'business_providers': get_business_providers(provider_settings),
        'google_configured': bool(get_google_api_key(provider_settings)),
        'geoapify_configured': bool(get_geoapify_api_key(provider_settings)),
        'apollo_enabled': provider_settings.apollo_enabled,
        'apollo_configured': bool(get_apollo_api_key(provider_settings)),
    }
