import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import (
    BulkManagerEnrichmentSerializer,
    BulkHotelEnrichmentSerializer,
    HotelEnrichmentSerializer,
    ManagerEnrichmentSerializer,
    NearbyHotelsQuerySerializer,
)
from .business_categories import get_business_categories, get_business_category
from .services.enrichment import enrich_hotel_from_website
from .services.enrichment.bulk import enrich_hotels_bulk
from .services.enrichment.base import EnrichmentError
from .services.openstreetmap import OpenStreetMapError, search_nearby_hotels
from .services.google_places import GooglePlacesError
from .services.geoapify import GeoapifyError
from .services.providers.orchestrator import (
    InvalidProviderSelectionError,
    MultiProviderSearchError,
    search_businesses_multi_provider,
)
from .services.providers import get_hotel_provider
from .services.providers.base import (
    HotelProviderConfigurationError,
    UnsupportedBusinessCategoryError,
)
from .provider_settings import get_apollo_api_key, get_provider_settings
from .services.people_enrichment import (
    search_decision_makers, search_decision_makers_multi_provider,
)
from .services.people_enrichment.bulk import (
    enrich_managers_bulk, enrich_managers_multi_provider_bulk,
)
from .services.people_enrichment.base import (
    PeopleEnrichmentConfigurationError,
    PeopleEnrichmentError,
)


logger = logging.getLogger(__name__)


@api_view(['GET'])
def health(request):
    return Response({
        'status': 'ok',
        'service': 'hotel-lead-collector',
    })


@api_view(['GET'])
def nearby_hotels(request):
    serializer = NearbyHotelsQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    params = serializer.validated_data

    try:
        if 'providers' not in params:
            hotels = get_hotel_provider().search_nearby_businesses(
                latitude=params['lat'], longitude=params['lng'], radius=params['radius'],
                category=params['category'],
            )
            return Response({
                'count': len(hotels), 'hotels': hotels, 'category': params['category'],
                'category_display_name': get_business_category(params['category'])['display_name'],
            })
        result = search_businesses_multi_provider(
            latitude=params['lat'], longitude=params['lng'], radius=params['radius'],
            category=params['category'], providers=params['providers'],
        )
    except HotelProviderConfigurationError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except UnsupportedBusinessCategoryError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except InvalidProviderSelectionError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except (MultiProviderSearchError, OpenStreetMapError, GooglePlacesError, GeoapifyError):
        logger.exception('Hotel provider search failed.')
        return Response(
            {'error': 'Unable to retrieve hotel data at this time.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response({
        'count': len(result['hotels']),
        'category': params['category'],
        'category_display_name': get_business_category(params['category'])['display_name'],
        **result,
    })


@api_view(['GET'])
def business_categories(request):
    return Response({
        'categories': [
            {'id': category['id'], 'name': category['display_name']}
            for category in get_business_categories()
        ],
    })


@api_view(['POST'])
def enrich_hotel(request):
    serializer = HotelEnrichmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    hotel = serializer.validated_data

    try:
        result = enrich_hotel_from_website(hotel)
    except EnrichmentError:
        logger.exception('Hotel website enrichment failed.')
        return Response(
            {
                'status': 'ERROR',
                'message': 'Unable to enrich this hotel at this time.',
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response(result)


@api_view(['POST'])
def enrich_hotels_bulk_api(request):
    serializer = BulkHotelEnrichmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(enrich_hotels_bulk(serializer.validated_data['hotels']))


@api_view(['POST'])
def enrich_managers(request):
    serializer = ManagerEnrichmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    params = serializer.validated_data

    if 'providers' in params:
        try:
            return Response(search_decision_makers_multi_provider(
                business={
                    'name': params['name'], 'website': params.get('website'),
                    'brand': params.get('brand'),
                    'address': params.get('address') or params.get('location'),
                    'latitude': params.get('latitude'), 'longitude': params.get('longitude'),
                }, category=params['category'], providers=params['providers'],
            ))
        except PeopleEnrichmentError as exc:
            return Response({'status': 'ERROR', 'message': str(exc)}, status=400)

    provider_settings = get_provider_settings()
    if not provider_settings.apollo_enabled:
        return Response({
            'status': 'DISABLED',
            'message': 'Apollo enrichment is disabled.',
        })
    apollo_api_key = get_apollo_api_key(provider_settings)
    if not apollo_api_key:
        return Response(
            {'status': 'ERROR', 'message': 'Apollo is enabled but no API key is configured.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        result = search_decision_makers(
            business={
                'name': params['name'],
                'website': params.get('website'),
                'brand': params.get('brand'),
                'address': params.get('address') or params.get('location'),
                'latitude': params.get('latitude'),
                'longitude': params.get('longitude'),
            },
            category=params['category'],
            api_key=apollo_api_key,
        )
    except PeopleEnrichmentConfigurationError:
        return Response(
            {'status': 'ERROR', 'message': 'Apollo is not configured.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except PeopleEnrichmentError:
        logger.exception('Apollo manager enrichment failed.')
        return Response(
            {'status': 'ERROR', 'message': 'Unable to search for managers at this time.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response(result)


@api_view(['POST'])
def enrich_managers_bulk_api(request):
    serializer = BulkManagerEnrichmentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    hotels = serializer.validated_data['hotels']

    if 'providers' in serializer.validated_data:
        return Response(enrich_managers_multi_provider_bulk(
            hotels, serializer.validated_data['providers'], get_provider_settings()
        ))

    provider_settings = get_provider_settings()
    if not provider_settings.apollo_enabled:
        return Response({
            'status': 'DISABLED',
            'message': 'Apollo enrichment is disabled. Configure it in Settings.',
        })
    apollo_api_key = get_apollo_api_key(provider_settings)
    if not apollo_api_key:
        return Response(
            {'status': 'ERROR', 'message': 'Apollo is enabled but no API key is configured.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(enrich_managers_bulk(hotels, apollo_api_key))
