from hotels.models import ProviderSettings
from hotels.provider_settings import (
    get_geoapify_api_key,
    get_google_api_key,
    get_provider_settings,
)

from .geoapify_provider import GeoapifyProvider
from .google_provider import GooglePlacesProvider
from .openstreetmap_provider import OpenStreetMapProvider


def get_hotel_provider(provider_settings=None):
    provider_settings = provider_settings or get_provider_settings()
    if provider_settings.hotel_provider == ProviderSettings.GEOAPIFY:
        return GeoapifyProvider(get_geoapify_api_key(provider_settings))
    if provider_settings.hotel_provider == ProviderSettings.GOOGLE:
        return GooglePlacesProvider(get_google_api_key(provider_settings))
    return OpenStreetMapProvider()
