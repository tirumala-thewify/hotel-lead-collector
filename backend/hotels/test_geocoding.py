from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from hotels.services.geocoding.nominatim import (
    NominatimError,
    RESULT_LIMIT,
    USER_AGENT,
    search_locations,
)


@override_settings(NOMINATIM_API_URL='https://nominatim.test/search')
class NominatimServiceTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def _response(self, data, status=200):
        response = Mock(status_code=status)
        response.json.return_value = data
        return response

    @patch('hotels.services.geocoding.nominatim.requests.get')
    def test_successful_location_search_and_normalization(self, mock_get):
        mock_get.return_value = self._response([{
            'name': 'Indira Gandhi International Airport',
            'display_name': 'Indira Gandhi International Airport, Delhi, India',
            'lat': '28.5562', 'lon': '77.1000', 'type': 'aerodrome',
            'licence': 'unused raw field',
        }])
        results = search_locations('Delhi Airport')
        self.assertEqual(results, [{
            'name': 'Indira Gandhi International Airport',
            'display_name': 'Indira Gandhi International Airport, Delhi, India',
            'latitude': 28.5562,
            'longitude': 77.1,
            'type': 'aerodrome',
        }])
        call = mock_get.call_args
        self.assertEqual(call.kwargs['params']['limit'], RESULT_LIMIT)
        self.assertEqual(call.kwargs['headers']['User-Agent'], USER_AGENT)

    @patch('hotels.services.geocoding.nominatim.requests.get')
    def test_multiple_location_results(self, mock_get):
        mock_get.return_value = self._response([
            {'display_name': 'Delhi Airport, India', 'lat': '28.5', 'lon': '77.1', 'type': 'aerodrome'},
            {'display_name': 'Delhi, India', 'lat': '28.6', 'lon': '77.2', 'type': 'city'},
        ])
        self.assertEqual(len(search_locations('Delhi')), 2)

    @patch('hotels.services.geocoding.nominatim.requests.get')
    def test_empty_results(self, mock_get):
        mock_get.return_value = self._response([])
        self.assertEqual(search_locations('No Such Place'), [])

    @patch('hotels.services.geocoding.nominatim.requests.get', side_effect=requests.Timeout)
    def test_timeout(self, mock_get):
        with self.assertRaisesMessage(NominatimError, 'timed out'):
            search_locations('Delhi')

    @patch('hotels.services.geocoding.nominatim.requests.get')
    def test_http_429(self, mock_get):
        mock_get.return_value = self._response([], 429)
        with self.assertRaisesMessage(NominatimError, 'rate limit'):
            search_locations('Delhi')

    @patch('hotels.services.geocoding.nominatim.requests.get')
    def test_http_500(self, mock_get):
        mock_get.return_value = self._response([], 500)
        with self.assertRaisesMessage(NominatimError, 'temporarily unavailable'):
            search_locations('Delhi')

    @patch('hotels.services.geocoding.nominatim.requests.get', side_effect=requests.ConnectionError)
    def test_connection_error(self, mock_get):
        with self.assertRaisesMessage(NominatimError, 'Could not connect'):
            search_locations('Delhi')

    @patch('hotels.services.geocoding.nominatim.requests.get')
    def test_invalid_json(self, mock_get):
        response = Mock(status_code=200)
        response.json.side_effect = ValueError
        mock_get.return_value = response
        with self.assertRaisesMessage(NominatimError, 'invalid JSON'):
            search_locations('Delhi')

    @patch('hotels.services.geocoding.nominatim.requests.get')
    def test_cache_prevents_duplicate_request(self, mock_get):
        mock_get.return_value = self._response([
            {'display_name': 'Delhi, India', 'lat': '28.6', 'lon': '77.2', 'type': 'city'},
        ])
        first = search_locations('Delhi')
        second = search_locations('delhi')
        self.assertEqual(first, second)
        mock_get.assert_called_once()


class LocationSearchAPITests(APITestCase):
    url = '/api/locations/search/'

    @patch('hotels.location_api.search_locations')
    def test_api_success(self, mock_search):
        mock_search.return_value = [{'name': 'Delhi', 'latitude': 28.6, 'longitude': 77.2}]
        response = self.client.get(self.url, {'q': 'Delhi Airport'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 1)

    def test_missing_q(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertIn('q', response.json())

    def test_empty_q(self):
        response = self.client.get(self.url, {'q': '   '})
        self.assertEqual(response.status_code, 400)

    def test_too_long_query(self):
        response = self.client.get(self.url, {'q': 'x' * 201})
        self.assertEqual(response.status_code, 400)
