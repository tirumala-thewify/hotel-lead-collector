import hashlib

import requests
from django.conf import settings
from django.core.cache import cache


USER_AGENT = 'HotelLeadCollector/0.1 (location search)'
REQUEST_TIMEOUT_SECONDS = 10
RESULT_LIMIT = 5
CACHE_SECONDS = 30 * 60


class NominatimError(Exception):
    """Raised when the configured geocoding service cannot complete a search."""


def _cache_key(query):
    digest = hashlib.sha256(query.casefold().encode()).hexdigest()
    return f'nominatim-search:{digest}'


def _normalize_result(result):
    if not isinstance(result, dict):
        return None
    try:
        latitude = float(result['lat'])
        longitude = float(result['lon'])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    display_name = result.get('display_name')
    if not display_name:
        return None
    return {
        'name': result.get('name') or display_name.split(',', 1)[0].strip(),
        'display_name': display_name,
        'latitude': latitude,
        'longitude': longitude,
        'type': result.get('type'),
    }


def search_locations(query):
    cache_key = _cache_key(query)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        response = requests.get(
            settings.NOMINATIM_API_URL,
            params={
                'q': query,
                'format': 'json',
                'limit': RESULT_LIMIT,
                'addressdetails': 1,
            },
            headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise NominatimError('The location search timed out.') from exc
    except requests.ConnectionError as exc:
        raise NominatimError('Could not connect to the location search service.') from exc
    except requests.RequestException as exc:
        raise NominatimError('The location search request failed.') from exc

    if response.status_code == 429:
        raise NominatimError('The location search rate limit was reached.')
    if 500 <= response.status_code <= 599:
        raise NominatimError('The location search service is temporarily unavailable.')
    if response.status_code != 200:
        raise NominatimError(
            f'The location search service returned HTTP {response.status_code}.'
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise NominatimError('The location search service returned invalid JSON.') from exc
    if not isinstance(data, list):
        raise NominatimError('The location search service returned a malformed response.')

    results = [normalized for item in data if (normalized := _normalize_result(item))]
    cache.set(cache_key, results, CACHE_SECONDS)
    return results
