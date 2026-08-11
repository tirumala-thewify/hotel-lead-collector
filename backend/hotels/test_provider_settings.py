from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from hotels.models import ProviderSettings
from hotels.services.providers import get_hotel_provider
from hotels.services.providers.base import HotelProviderConfigurationError
from hotels.services.providers.google_provider import GooglePlacesProvider
from hotels.services.providers.openstreetmap_provider import OpenStreetMapProvider


@override_settings(GOOGLE_MAPS_API_KEY='', APOLLO_API_KEY='')
class ProviderSettingsAPITests(APITestCase):
    url = '/api/settings/providers/'

    def test_default_provider_is_openstreetmap(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['hotel_provider'], 'openstreetmap')
        self.assertFalse(response.json()['apollo_enabled'])

    def test_settings_get_does_not_expose_api_keys(self):
        provider_settings = ProviderSettings.load()
        provider_settings.set_google_api_key('secret-google-key')
        provider_settings.set_apollo_api_key('secret-apollo-key')
        provider_settings.save()
        data = self.client.get(self.url).json()
        self.assertNotIn('google_api_key', data)
        self.assertNotIn('apollo_api_key', data)
        self.assertNotIn('secret-google-key', str(data))
        self.assertNotIn('secret-apollo-key', str(data))

    def test_save_google_key_encrypted(self):
        response = self.client.put(self.url, {'google_api_key': 'google-secret'}, format='json')
        self.assertEqual(response.status_code, 200)
        provider_settings = ProviderSettings.load()
        self.assertNotEqual(provider_settings.google_api_key_encrypted, 'google-secret')
        self.assertEqual(provider_settings.get_google_api_key(), 'google-secret')

    def test_save_apollo_key_encrypted(self):
        response = self.client.put(self.url, {'apollo_api_key': 'apollo-secret'}, format='json')
        self.assertEqual(response.status_code, 200)
        provider_settings = ProviderSettings.load()
        self.assertNotEqual(provider_settings.apollo_api_key_encrypted, 'apollo-secret')
        self.assertEqual(provider_settings.get_apollo_api_key(), 'apollo-secret')

    def test_google_configured_flag(self):
        data = self.client.put(
            self.url, {'google_api_key': 'google-secret'}, format='json'
        ).json()
        self.assertTrue(data['google_configured'])

    def test_apollo_configured_flag(self):
        data = self.client.put(
            self.url, {'apollo_api_key': 'apollo-secret'}, format='json'
        ).json()
        self.assertTrue(data['apollo_configured'])


@override_settings(GOOGLE_MAPS_API_KEY='', APOLLO_API_KEY='')
class HotelProviderSelectionTests(TestCase):
    def test_openstreetmap_provider_selected(self):
        self.assertIsInstance(get_hotel_provider(ProviderSettings.load()), OpenStreetMapProvider)

    def test_google_provider_selected(self):
        settings_record = ProviderSettings.load()
        settings_record.hotel_provider = ProviderSettings.GOOGLE
        settings_record.set_google_api_key('google-secret')
        settings_record.save()
        self.assertIsInstance(get_hotel_provider(settings_record), GooglePlacesProvider)

    def test_google_selected_without_key(self):
        settings_record = ProviderSettings.load()
        settings_record.hotel_provider = ProviderSettings.GOOGLE
        settings_record.save()
        with self.assertRaisesMessage(
            HotelProviderConfigurationError,
            'Google Places is selected but no API key is configured.',
        ):
            get_hotel_provider(settings_record)

    @patch('hotels.services.providers.google_provider.search_nearby_hotels')
    def test_google_service_receives_configured_key(self, mock_search):
        mock_search.return_value = []
        settings_record = ProviderSettings.load()
        settings_record.hotel_provider = ProviderSettings.GOOGLE
        settings_record.set_google_api_key('database-google-key')
        settings_record.save()
        provider = get_hotel_provider(settings_record)
        provider.search_nearby_hotels(28.5, 77.1, 5000)
        mock_search.assert_called_once_with(
            28.5, 77.1, 5000, api_key='database-google-key'
        )


@override_settings(APOLLO_API_KEY='')
class ApolloSettingsTests(APITestCase):
    url = '/api/hotels/enrich-managers/'
    payload = {'name': 'Roseate House'}

    def test_apollo_disabled(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'DISABLED')

    def test_apollo_enabled_without_key(self):
        settings_record = ProviderSettings.load()
        settings_record.apollo_enabled = True
        settings_record.save()
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'ERROR')

    @patch('hotels.views.search_decision_makers')
    def test_apollo_enabled_with_database_key(self, mock_search):
        mock_search.return_value = {
            'hotel_name': 'Roseate House', 'contacts': [], 'status': 'NOT_FOUND'
        }
        settings_record = ProviderSettings.load()
        settings_record.apollo_enabled = True
        settings_record.set_apollo_api_key('database-apollo-key')
        settings_record.save()
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'NOT_FOUND')
        self.assertEqual(mock_search.call_args.kwargs['api_key'], 'database-apollo-key')
