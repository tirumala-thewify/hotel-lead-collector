from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase

from hotels.services.geoapify import (
    GEOAPIFY_PLACES_URL,
    REQUEST_TIMEOUT_SECONDS,
    RESULT_LIMIT,
    GeoapifyError,
    search_nearby_businesses,
)
from hotels.services.geoapify_categories import (
    GEOAPIFY_CATEGORY_MAPPINGS,
    get_geoapify_categories,
)
from hotels.services.providers.base import (
    HotelProviderConfigurationError,
    UnsupportedBusinessCategoryError,
)
from hotels.services.providers.geoapify_provider import GeoapifyProvider


class GeoapifyCategoryTests(SimpleTestCase):
    def test_all_internal_categories_have_documented_mappings(self):
        self.assertEqual(len(GEOAPIFY_CATEGORY_MAPPINGS), 17)
        self.assertEqual(get_geoapify_categories('restaurants'), ('catering.restaurant',))
        self.assertEqual(
            get_geoapify_categories('universities_colleges'),
            ('education.university', 'education.college'),
        )

    def test_unknown_category_is_unsupported(self):
        with self.assertRaisesMessage(ValueError, 'not supported by Geoapify'):
            get_geoapify_categories('invalid_category')


class GeoapifyProviderTests(SimpleTestCase):
    def test_missing_key_is_rejected(self):
        with self.assertRaisesMessage(
            HotelProviderConfigurationError, 'no API key is configured'
        ):
            GeoapifyProvider('')

    @patch('hotels.services.providers.geoapify_provider.search_nearby_businesses')
    def test_provider_forwards_supported_search(self, mock_search):
        mock_search.return_value = []
        provider = GeoapifyProvider('secret-key')
        provider.search_nearby_businesses(28.5, 77.1, 2000, 'restaurants')
        mock_search.assert_called_once_with(
            28.5, 77.1, 2000, 'restaurants', api_key='secret-key'
        )

    def test_provider_rejects_unsupported_category_without_request(self):
        provider = GeoapifyProvider('secret-key')
        with self.assertRaisesMessage(
            UnsupportedBusinessCategoryError, 'not supported by Geoapify'
        ):
            provider.search_nearby_businesses(28.5, 77.1, 2000, 'invalid')


class GeoapifyServiceTests(SimpleTestCase):
    def _response(self, features):
        response = Mock(status_code=200)
        response.json.return_value = {'type': 'FeatureCollection', 'features': features}
        return response

    @patch('hotels.services.geoapify.requests.get')
    def test_successful_search_is_normalized_and_sorted(self, mock_get):
        mock_get.return_value = self._response([
            {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [77.11, 28.56]},
                'properties': {
                    'place_id': 'far', 'name': 'Far Restaurant',
                    'formatted': 'Far Road, Delhi', 'distance': 1200,
                    'contact': {'phone': '+91 111', 'email': 'far@example.com'},
                    'website': 'https://far.example', 'brand': 'Far Brand',
                },
            },
            {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': [77.101, 28.557]},
                'properties': {
                    'place_id': 'near', 'name': 'Near Restaurant', 'distance': 100,
                },
            },
        ])

        businesses = search_nearby_businesses(
            28.5562, 77.1, 2000, 'restaurants', 'secret-key'
        )

        self.assertEqual([item['name'] for item in businesses], [
            'Near Restaurant', 'Far Restaurant',
        ])
        far = businesses[1]
        self.assertEqual(far['address'], 'Far Road, Delhi')
        self.assertEqual(far['phone'], '+91 111')
        self.assertEqual(far['email'], 'far@example.com')
        self.assertEqual(far['website'], 'https://far.example')
        self.assertEqual(far['distance_km'], 1.2)
        self.assertEqual(far['source'], 'Geoapify')
        self.assertEqual(far['category'], 'restaurants')
        mock_get.assert_called_once_with(
            GEOAPIFY_PLACES_URL,
            params={
                'categories': 'catering.restaurant',
                'filter': 'circle:77.1,28.5562,2000',
                'bias': 'proximity:77.1,28.5562',
                'limit': RESULT_LIMIT,
                'apiKey': 'secret-key',
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

    @patch('hotels.services.geoapify.requests.get')
    def test_missing_fields_remain_none_and_distance_uses_haversine(self, mock_get):
        mock_get.return_value = self._response([{
            'geometry': {'type': 'Point', 'coordinates': [77.1, 28.5662]},
            'properties': {'place_id': 'minimal', 'name': 'Minimal'},
        }])
        business = search_nearby_businesses(
            28.5562, 77.1, 2000, 'restaurants', 'key'
        )[0]
        self.assertIsNone(business['phone'])
        self.assertIsNone(business['website'])
        self.assertIsNone(business['address'])
        self.assertEqual(business['distance_km'], 1.11)

    @patch('hotels.services.geoapify.requests.get')
    def test_datasource_contact_fields_are_preserved(self, mock_get):
        mock_get.return_value = self._response([{
            'geometry': {'type': 'Point', 'coordinates': [77.1, 28.5562]},
            'properties': {
                'place_id': 'raw-contact',
                'name': 'Raw Contact Restaurant',
                'datasource': {'raw': {
                    'phone': '+91 222',
                    'website': 'https://raw.example',
                    'email': 'raw@example.com',
                }},
            },
        }])
        business = search_nearby_businesses(
            28.5562, 77.1, 2000, 'restaurants', 'key'
        )[0]
        self.assertEqual(business['phone'], '+91 222')
        self.assertEqual(business['website'], 'https://raw.example')
        self.assertEqual(business['email'], 'raw@example.com')

    @patch('hotels.services.geoapify.requests.get')
    def test_authentication_errors_are_clean(self, mock_get):
        for status in (401, 403):
            with self.subTest(status=status):
                mock_get.return_value = Mock(status_code=status)
                with self.assertRaisesMessage(GeoapifyError, 'denied access'):
                    search_nearby_businesses(1, 2, 1000, 'restaurants', 'key')

    @patch('hotels.services.geoapify.requests.get')
    def test_rate_limit_error_is_clean(self, mock_get):
        mock_get.return_value = Mock(status_code=429)
        with self.assertRaisesMessage(GeoapifyError, 'quota or rate limit'):
            search_nearby_businesses(1, 2, 1000, 'restaurants', 'key')

    @patch('hotels.services.geoapify.requests.get')
    def test_server_error_is_clean(self, mock_get):
        mock_get.return_value = Mock(status_code=500)
        with self.assertRaisesMessage(GeoapifyError, 'temporarily unavailable'):
            search_nearby_businesses(1, 2, 1000, 'restaurants', 'key')

    @patch('hotels.services.geoapify.requests.get', side_effect=requests.Timeout)
    def test_timeout_is_clean(self, mock_get):
        with self.assertRaisesMessage(GeoapifyError, 'timed out'):
            search_nearby_businesses(1, 2, 1000, 'restaurants', 'key')

    @patch('hotels.services.geoapify.requests.get', side_effect=requests.ConnectionError)
    def test_connection_error_is_clean(self, mock_get):
        with self.assertRaisesMessage(GeoapifyError, 'Could not connect'):
            search_nearby_businesses(1, 2, 1000, 'restaurants', 'key')

    @patch('hotels.services.geoapify.requests.get')
    def test_malformed_json_is_rejected(self, mock_get):
        response = Mock(status_code=200)
        response.json.side_effect = ValueError
        mock_get.return_value = response
        with self.assertRaisesMessage(GeoapifyError, 'invalid JSON'):
            search_nearby_businesses(1, 2, 1000, 'restaurants', 'key')

    @patch('hotels.services.geoapify.requests.get')
    def test_malformed_structure_is_rejected(self, mock_get):
        response = Mock(status_code=200)
        response.json.return_value = {'features': None}
        mock_get.return_value = response
        with self.assertRaisesMessage(GeoapifyError, 'invalid response structure'):
            search_nearby_businesses(1, 2, 1000, 'restaurants', 'key')
