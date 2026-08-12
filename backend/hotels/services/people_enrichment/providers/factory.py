from hotels.provider_settings import get_apollo_api_key, get_zoominfo_api_key

from ..apollo import ApolloPeopleEnrichmentProvider
from ..zoominfo import ZoomInfoPeopleEnrichmentProvider


def get_people_provider(provider_name, provider_settings, zoominfo_transport=None):
    if provider_name == 'apollo':
        return ApolloPeopleEnrichmentProvider(get_apollo_api_key(provider_settings))
    if provider_name == 'zoominfo':
        return ZoomInfoPeopleEnrichmentProvider(
            get_zoominfo_api_key(provider_settings), transport=zoominfo_transport
        )
    raise ValueError('Unsupported people enrichment provider.')
