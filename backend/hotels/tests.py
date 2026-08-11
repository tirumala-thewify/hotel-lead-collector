from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings
from django.core.cache import cache
from rest_framework.test import APITestCase

from hotels.services.google_places import (
    FIELD_MASK,
    NEARBY_SEARCH_URL,
    REQUEST_TIMEOUT_SECONDS,
    GooglePlacesError,
    search_nearby_hotels,
)
from hotels.services.openstreetmap import (
    MAX_RADIUS_METERS,
    REQUEST_TIMEOUT_SECONDS as OSM_TIMEOUT,
    USER_AGENT,
    OpenStreetMapError,
    calculate_distance_km,
    search_nearby_hotels as search_osm_hotels,
)


@override_settings(GOOGLE_MAPS_API_KEY='test-api-key')
class GooglePlacesServiceTests(SimpleTestCase):
    @patch('hotels.services.google_places.requests.post')
    def test_successful_google_response(self, mock_post):
        response = Mock(status_code=200)
        response.json.return_value = {
            'places': [{
                'id': 'place-123',
                'displayName': {'text': 'Airport Hotel', 'languageCode': 'en'},
                'formattedAddress': 'Delhi Airport, New Delhi',
                'location': {'latitude': 28.556, 'longitude': 77.1},
                'googleMapsUri': 'https://maps.google.com/example',
            }],
        }
        mock_post.return_value = response

        hotels = search_nearby_hotels(28.5562, 77.1, 5000)

        self.assertEqual(hotels, [{
            'place_id': 'place-123',
            'name': 'Airport Hotel',
            'address': 'Delhi Airport, New Delhi',
            'latitude': 28.556,
            'longitude': 77.1,
            'google_maps_url': 'https://maps.google.com/example',
        }])
        mock_post.assert_called_once_with(
            NEARBY_SEARCH_URL,
            headers={
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': 'test-api-key',
                'X-Goog-FieldMask': FIELD_MASK,
            },
            json={
                'includedTypes': ['hotel'],
                'maxResultCount': 20,
                'locationRestriction': {
                    'circle': {
                        'center': {'latitude': 28.5562, 'longitude': 77.1},
                        'radius': 5000,
                    },
                },
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    @patch('hotels.services.google_places.requests.post')
    def test_empty_places_response(self, mock_post):
        response = Mock(status_code=200)
        response.json.return_value = {}
        mock_post.return_value = response

        self.assertEqual(search_nearby_hotels(28.5562, 77.1, 5000), [])

    @override_settings(GOOGLE_MAPS_API_KEY='')
    @patch('hotels.services.google_places.requests.post')
    def test_missing_api_key(self, mock_post):
        with self.assertRaisesMessage(GooglePlacesError, 'GOOGLE_MAPS_API_KEY is not configured.'):
            search_nearby_hotels(28.5562, 77.1, 5000)
        mock_post.assert_not_called()

    @patch('hotels.services.google_places.requests.post')
    def test_google_http_error(self, mock_post):
        mock_post.return_value = Mock(status_code=403)

        with self.assertRaisesMessage(GooglePlacesError, 'Google Places denied access.'):
            search_nearby_hotels(28.5562, 77.1, 5000)

    @patch('hotels.services.google_places.requests.post')
    def test_request_timeout(self, mock_post):
        mock_post.side_effect = requests.Timeout

        with self.assertRaisesMessage(GooglePlacesError, 'Google Places request timed out.'):
            search_nearby_hotels(28.5562, 77.1, 5000)

    @patch('hotels.services.google_places.requests.post')
    def test_network_error(self, mock_post):
        mock_post.side_effect = requests.ConnectionError

        with self.assertRaisesMessage(GooglePlacesError, 'Could not connect to Google Places.'):
            search_nearby_hotels(28.5562, 77.1, 5000)


@override_settings(OVERPASS_API_URL='https://overpass.test/api/interpreter')
class OpenStreetMapServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def _response(self, elements):
        response = Mock(status_code=200)
        response.json.return_value = {'elements': elements}
        return response

    @patch('hotels.services.openstreetmap.requests.post')
    def test_successful_overpass_response(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 1, 'lat': 28.55, 'lon': 77.1,
             'tags': {'tourism': 'hotel', 'name': 'Airport Hotel'}},
        ])

        hotels = search_osm_hotels(28.5562, 77.1, 5000)

        self.assertEqual(len(hotels), 1)
        self.assertEqual(hotels[0]['source'], 'OpenStreetMap')
        call = mock_post.call_args
        self.assertEqual(call.args[0], 'https://overpass.test/api/interpreter')
        self.assertEqual(call.kwargs['headers'], {'User-Agent': USER_AGENT})
        self.assertEqual(call.kwargs['timeout'], OSM_TIMEOUT)
        query = call.kwargs['data']['data']
        self.assertIn('nwr["tourism"="hotel"]', query)
        self.assertIn('out center tags;', query)

    @override_settings(OVERPASS_API_URLS=(
        'https://primary.test/api/interpreter',
        'https://fallback.test/api/interpreter',
    ))
    @patch('hotels.services.openstreetmap.requests.post')
    def test_retryable_http_statuses_use_fallback(self, mock_post):
        for status in (504, 503, 502, 429):
            with self.subTest(status=status):
                cache.clear()
                mock_post.reset_mock()
                mock_post.side_effect = [Mock(status_code=status), self._response([])]
                self.assertEqual(search_osm_hotels(19.090138, 72.863822, 2000), [])
                self.assertEqual(mock_post.call_count, 2)
                self.assertEqual(
                    mock_post.call_args_list[1].args[0],
                    'https://fallback.test/api/interpreter',
                )

    @override_settings(OVERPASS_API_URLS=('https://primary.test', 'https://fallback.test'))
    @patch('hotels.services.openstreetmap.requests.post')
    def test_timeout_uses_fallback(self, mock_post):
        mock_post.side_effect = [requests.Timeout, self._response([])]
        self.assertEqual(search_osm_hotels(19.09, 72.86, 2000), [])
        self.assertEqual(mock_post.call_count, 2)

    @override_settings(OVERPASS_API_URLS=('https://primary.test', 'https://fallback.test'))
    @patch('hotels.services.openstreetmap.requests.post')
    def test_connection_failure_uses_fallback(self, mock_post):
        mock_post.side_effect = [requests.ConnectionError, self._response([])]
        self.assertEqual(search_osm_hotels(19.09, 72.86, 2000), [])
        self.assertEqual(mock_post.call_count, 2)

    @override_settings(OVERPASS_API_URLS=('https://primary.test', 'https://fallback.test'))
    @patch('hotels.services.openstreetmap.requests.post')
    def test_http_400_does_not_use_fallback(self, mock_post):
        mock_post.return_value = Mock(status_code=400)
        with self.assertRaisesMessage(OpenStreetMapError, 'HTTP 400'):
            search_osm_hotels(19.09, 72.86, 2000)
        mock_post.assert_called_once()

    @override_settings(OVERPASS_API_URLS=('https://primary.test', 'https://fallback.test'))
    @patch('hotels.services.openstreetmap.requests.post')
    def test_primary_and_fallback_failure(self, mock_post):
        mock_post.side_effect = [Mock(status_code=504), Mock(status_code=503)]
        with self.assertRaises(OpenStreetMapError):
            search_osm_hotels(19.09, 72.86, 2000)
        self.assertEqual(mock_post.call_count, 2)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_success_is_cached_and_cache_hit_makes_no_request(self, mock_post):
        mock_post.return_value = self._response([])
        self.assertEqual(search_osm_hotels(19.0901381, 72.8638221, 2000), [])
        mock_post.reset_mock()
        self.assertEqual(search_osm_hotels(19.09013809, 72.86382209, 2000), [])
        mock_post.assert_not_called()

    @override_settings(OVERPASS_API_URLS=('https://primary.test', 'https://fallback.test'))
    @patch('hotels.services.openstreetmap.requests.post')
    def test_error_is_not_cached(self, mock_post):
        mock_post.side_effect = [
            Mock(status_code=504), Mock(status_code=504), self._response([]),
        ]
        with self.assertRaises(OpenStreetMapError):
            search_osm_hotels(19.09, 72.86, 2000)
        self.assertEqual(search_osm_hotels(19.09, 72.86, 2000), [])
        self.assertEqual(mock_post.call_count, 3)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_cache_key_changes_for_radius_and_coordinates(self, mock_post):
        mock_post.return_value = self._response([])
        search_osm_hotels(19.09, 72.86, 2000)
        search_osm_hotels(19.09, 72.86, 3000)
        search_osm_hotels(19.10, 72.86, 2000)
        self.assertEqual(mock_post.call_count, 3)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_empty_elements_response(self, mock_post):
        mock_post.return_value = self._response([])
        self.assertEqual(search_osm_hotels(28.5562, 77.1, 5000), [])

    @patch('hotels.services.openstreetmap.requests.post')
    def test_node_hotel_parsing(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 10, 'lat': 28.5, 'lon': 77.2, 'tags': {}},
        ])
        hotel = search_osm_hotels(28.5, 77.2, 1000)[0]
        self.assertEqual((hotel['osm_type'], hotel['osm_id']), ('node', 10))
        self.assertEqual((hotel['latitude'], hotel['longitude']), (28.5, 77.2))

    @patch('hotels.services.openstreetmap.requests.post')
    def test_way_hotel_parsing_uses_center(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'way', 'id': 20, 'center': {'lat': 28.6, 'lon': 77.3}, 'tags': {}},
        ])
        hotel = search_osm_hotels(28.5, 77.2, 1000)[0]
        self.assertEqual((hotel['latitude'], hotel['longitude']), (28.6, 77.3))

    @patch('hotels.services.openstreetmap.requests.post')
    def test_address_construction(self, mock_post):
        mock_post.return_value = self._response([{
            'type': 'node', 'id': 30, 'lat': 1, 'lon': 2,
            'tags': {'addr:housenumber': '12', 'addr:street': 'Airport Road',
                     'addr:suburb': 'Aerocity', 'addr:city': 'New Delhi',
                     'addr:state': 'Delhi', 'addr:postcode': '110037'},
        }])
        hotel = search_osm_hotels(1, 2, 1000)[0]
        self.assertEqual(hotel['address'], '12 Airport Road, Aerocity, New Delhi, Delhi, 110037')

    @patch('hotels.services.openstreetmap.requests.post')
    def test_phone_and_contact_phone_parsing(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 40, 'lat': 1, 'lon': 2,
             'tags': {'phone': '', 'contact:phone': '+91 123'}},
        ])
        self.assertEqual(search_osm_hotels(1, 2, 1000)[0]['phone'], '+91 123')

    @patch('hotels.services.openstreetmap.requests.post')
    def test_email_and_contact_email_parsing(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 41, 'lat': 1, 'lon': 2,
             'tags': {'email': '', 'contact:email': 'info@example.com'}},
        ])
        self.assertEqual(search_osm_hotels(1, 2, 1000)[0]['email'], 'info@example.com')

    @patch('hotels.services.openstreetmap.requests.post')
    def test_website_and_contact_website_parsing(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 42, 'lat': 1, 'lon': 2,
             'tags': {'website': '', 'contact:website': 'https://example.com'}},
        ])
        self.assertEqual(search_osm_hotels(1, 2, 1000)[0]['website'], 'https://example.com')

    @patch('hotels.services.openstreetmap.requests.post')
    def test_invalid_latitude(self, mock_post):
        with self.assertRaisesMessage(OpenStreetMapError, 'Latitude must be between'):
            search_osm_hotels(91, 77.1, 1000)
        mock_post.assert_not_called()

    @patch('hotels.services.openstreetmap.requests.post')
    def test_invalid_longitude(self, mock_post):
        with self.assertRaisesMessage(OpenStreetMapError, 'Longitude must be between'):
            search_osm_hotels(28.5, 181, 1000)
        mock_post.assert_not_called()

    @patch('hotels.services.openstreetmap.requests.post')
    def test_invalid_radius(self, mock_post):
        with self.assertRaisesMessage(OpenStreetMapError, 'Radius must be positive.'):
            search_osm_hotels(28.5, 77.1, 0)
        mock_post.assert_not_called()

    @patch('hotels.services.openstreetmap.requests.post')
    def test_radius_greater_than_maximum(self, mock_post):
        with self.assertRaisesMessage(OpenStreetMapError, str(MAX_RADIUS_METERS)):
            search_osm_hotels(28.5, 77.1, MAX_RADIUS_METERS + 1)
        mock_post.assert_not_called()

    @patch('hotels.services.openstreetmap.requests.post', side_effect=requests.Timeout)
    def test_timeout(self, mock_post):
        with self.assertRaisesMessage(OpenStreetMapError, 'timed out'):
            search_osm_hotels(28.5, 77.1, 1000)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_http_429(self, mock_post):
        mock_post.return_value = Mock(status_code=429)
        with self.assertRaisesMessage(OpenStreetMapError, 'rate limit'):
            search_osm_hotels(28.5, 77.1, 1000)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_http_500(self, mock_post):
        mock_post.return_value = Mock(status_code=500)
        with self.assertRaisesMessage(OpenStreetMapError, 'unavailable'):
            search_osm_hotels(28.5, 77.1, 1000)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_invalid_json(self, mock_post):
        response = Mock(status_code=200)
        response.json.side_effect = ValueError
        mock_post.return_value = response
        with self.assertRaisesMessage(OpenStreetMapError, 'invalid JSON'):
            search_osm_hotels(28.5, 77.1, 1000)

    def test_haversine_distance_calculation(self):
        self.assertEqual(calculate_distance_km(28.5562, 77.1, 28.5662, 77.1), 1.11)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_identical_normalized_names_within_150m_are_deduplicated(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 101, 'lat': 28.5562, 'lon': 77.1,
             'tags': {'name': 'Lemon Tree Premier, Delhi Airport'}},
            {'type': 'way', 'id': 102, 'center': {'lat': 28.5567, 'lon': 77.1},
             'tags': {'name': '  lemon tree premier delhi airport  '}},
        ])
        self.assertEqual(len(search_osm_hotels(28.5562, 77.1, 5000)), 1)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_same_name_hotels_far_apart_are_not_deduplicated(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 103, 'lat': 28.5562, 'lon': 77.1,
             'tags': {'name': 'Airport Hotel'}},
            {'type': 'way', 'id': 104, 'center': {'lat': 28.5762, 'lon': 77.1},
             'tags': {'name': 'Airport Hotel'}},
        ])
        self.assertEqual(len(search_osm_hotels(28.5562, 77.1, 5000)), 2)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_duplicate_records_merge_useful_fields(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 105, 'lat': 28.5562, 'lon': 77.1,
             'tags': {'name': 'Merge Hotel', 'phone': '+91 123'}},
            {'type': 'way', 'id': 106, 'center': {'lat': 28.5563, 'lon': 77.1},
             'tags': {'name': 'Merge Hotel', 'website': 'https://hotel.example'}},
        ])
        hotel = search_osm_hotels(28.5562, 77.1, 5000)[0]
        self.assertEqual(hotel['phone'], '+91 123')
        self.assertEqual(hotel['website'], 'https://hotel.example')

    @patch('hotels.services.openstreetmap.requests.post')
    def test_richer_duplicate_record_is_preferred(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 107, 'lat': 28.5562, 'lon': 77.1,
             'tags': {'name': 'Rich Hotel', 'phone': '+91 123'}},
            {'type': 'relation', 'id': 108, 'center': {'lat': 28.5563, 'lon': 77.1},
             'tags': {'name': 'Rich Hotel', 'website': 'https://rich.example',
                      'brand': 'Rich Brand', 'stars': '5'}},
        ])
        hotel = search_osm_hotels(28.5562, 77.1, 5000)[0]
        self.assertEqual((hotel['osm_type'], hotel['osm_id']), ('relation', 108))
        self.assertEqual(hotel['phone'], '+91 123')

    @patch('hotels.services.openstreetmap.requests.post')
    def test_distance_is_added(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 109, 'lat': 28.5662, 'lon': 77.1,
             'tags': {'name': 'Distance Hotel'}},
        ])
        self.assertEqual(search_osm_hotels(28.5562, 77.1, 5000)[0]['distance_km'], 1.11)

    @patch('hotels.services.openstreetmap.requests.post')
    def test_results_are_sorted_nearest_to_farthest(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'node', 'id': 110, 'lat': 28.5762, 'lon': 77.1,
             'tags': {'name': 'Far Hotel'}},
            {'type': 'node', 'id': 111, 'lat': 28.5612, 'lon': 77.1,
             'tags': {'name': 'Near Hotel'}},
        ])
        hotels = search_osm_hotels(28.5562, 77.1, 5000)
        self.assertEqual([hotel['name'] for hotel in hotels], ['Near Hotel', 'Far Hotel'])

    @patch('hotels.services.openstreetmap.requests.post')
    def test_missing_coordinates_are_safe_and_sort_last(self, mock_post):
        mock_post.return_value = self._response([
            {'type': 'way', 'id': 112, 'tags': {'name': 'Unknown Hotel'}},
            {'type': 'node', 'id': 113, 'lat': 28.5562, 'lon': 77.1,
             'tags': {'name': 'Known Hotel'}},
        ])
        hotels = search_osm_hotels(28.5562, 77.1, 5000)
        self.assertEqual(hotels[0]['name'], 'Known Hotel')
        self.assertIsNone(hotels[-1]['distance_km'])


class NearbyHotelsAPITests(APITestCase):
    url = '/api/hotels/nearby/'

    @patch('hotels.views.get_hotel_provider')
    def test_successful_nearby_response(self, mock_get_provider):
        hotel = {
            'osm_type': 'node',
            'osm_id': 123,
            'name': 'Example Hotel',
            'address': 'Aerocity, New Delhi',
            'latitude': 28.55,
            'longitude': 77.10,
            'phone': None,
            'email': None,
            'website': None,
            'brand': None,
            'stars': None,
            'source': 'OpenStreetMap',
        }
        mock_get_provider.return_value.search_nearby_hotels.return_value = [hotel]

        response = self.client.get(self.url, {
            'lat': '28.5562', 'lng': '77.1000', 'radius': '5000',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'count': 1, 'hotels': [hotel]})
        mock_get_provider.return_value.search_nearby_hotels.assert_called_once_with(
            latitude=28.5562,
            longitude=77.1,
            radius=5000.0,
        )

    @patch('hotels.views.get_hotel_provider')
    def test_no_hotels(self, mock_get_provider):
        mock_get_provider.return_value.search_nearby_hotels.return_value = []
        response = self.client.get(self.url, {
            'lat': 28.5562, 'lng': 77.1, 'radius': 5000,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'count': 0, 'hotels': []})

    def test_missing_lat(self):
        response = self.client.get(self.url, {'lng': 77.1, 'radius': 5000})
        self.assertEqual(response.status_code, 400)
        self.assertIn('lat', response.json())

    def test_missing_lng(self):
        response = self.client.get(self.url, {'lat': 28.5, 'radius': 5000})
        self.assertEqual(response.status_code, 400)
        self.assertIn('lng', response.json())

    def test_missing_radius(self):
        response = self.client.get(self.url, {'lat': 28.5, 'lng': 77.1})
        self.assertEqual(response.status_code, 400)
        self.assertIn('radius', response.json())

    def test_invalid_latitude(self):
        response = self.client.get(self.url, {
            'lat': 91, 'lng': 77.1, 'radius': 5000,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('lat', response.json())

    def test_invalid_longitude(self):
        response = self.client.get(self.url, {
            'lat': 28.5, 'lng': -181, 'radius': 5000,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('lng', response.json())

    def test_invalid_radius(self):
        response = self.client.get(self.url, {
            'lat': 28.5, 'lng': 77.1, 'radius': 0,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('radius', response.json())

    def test_radius_too_large(self):
        response = self.client.get(self.url, {
            'lat': 28.5, 'lng': 77.1, 'radius': 20001,
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('radius', response.json())

    @patch('hotels.views.get_hotel_provider')
    def test_openstreetmap_error(self, mock_get_provider):
        mock_get_provider.return_value.search_nearby_hotels.side_effect = OpenStreetMapError(
            'Overpass failed internally.'
        )

        response = self.client.get(self.url, {
            'lat': 28.5, 'lng': 77.1, 'radius': 5000,
        })

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {'error': 'Unable to retrieve hotel data at this time.'},
        )
