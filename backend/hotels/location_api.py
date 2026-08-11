import logging

from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services.geocoding import search_locations
from .services.geocoding.nominatim import NominatimError


logger = logging.getLogger(__name__)


class LocationSearchSerializer(serializers.Serializer):
    q = serializers.CharField(required=True, min_length=2, max_length=200, trim_whitespace=True)


@api_view(['GET'])
def location_search(request):
    serializer = LocationSearchSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    try:
        results = search_locations(serializer.validated_data['q'])
    except NominatimError:
        logger.exception('Nominatim location search failed.')
        return Response(
            {'error': 'Location search is temporarily unavailable.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    return Response({'results': results})
