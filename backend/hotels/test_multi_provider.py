from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APITestCase

from hotels.models import ProviderSettings
from hotels.provider_settings import get_business_providers
from hotels.services.providers.orchestrator import (
    DEDUPLICATION_DISTANCE_KM,
    MultiProviderSearchError,
    search_businesses_multi_provider,
)


def business(source, name='Acme Hospital', **values):
    return {
        'name': name, 'source': source, 'address': values.pop('address', '1 Main Road'),
        'latitude': values.pop('latitude', 28.5), 'longitude': values.pop('longitude', 77.1),
        'distance_km': values.pop('distance_km', 1.0), 'phone': None, 'email': None,
        'website': None, 'brand': None, 'stars': None, **values,
    }


@override_settings(GOOGLE_MAPS_API_KEY='', GEOAPIFY_API_KEY='')
class MultiProviderSettingsTests(APITestCase):
    url = '/api/settings/providers/'

    def test_one_and_multiple_provider_selection(self):
        self.assertEqual(self.client.put(self.url, {
            'business_providers': ['openstreetmap'],
        }, format='json').status_code, 200)
        response = self.client.put(self.url, {
            'geoapify_api_key': 'key',
            'business_providers': ['openstreetmap', 'geoapify'],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['business_providers'], ['openstreetmap', 'geoapify'])

    def test_zero_providers_rejected(self):
        response = self.client.put(self.url, {'business_providers': []}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Select at least one business data provider.', str(response.json()))

    def test_unconfigured_keyed_providers_rejected(self):
        for provider in ('geoapify', 'google'):
            with self.subTest(provider=provider):
                response = self.client.put(
                    self.url, {'business_providers': [provider]}, format='json'
                )
                self.assertEqual(response.status_code, 400)

    def test_legacy_field_is_fallback_and_secrets_remain_hidden(self):
        settings_record = ProviderSettings.load()
        settings_record.hotel_provider = 'geoapify'
        settings_record.business_providers = []
        settings_record.set_geoapify_api_key('secret')
        settings_record.save()
        self.assertEqual(get_business_providers(settings_record), ['geoapify'])
        payload = self.client.get(self.url).json()
        self.assertEqual(payload['business_providers'], ['geoapify'])
        self.assertNotIn('secret', str(payload))


class MultiProviderOrchestrationTests(SimpleTestCase):
    def run_search(self, providers, results=None, failures=()):
        results = results or {}

        def factory(provider, _settings):
            instance = Mock()
            if provider in failures:
                instance.search_nearby_businesses.side_effect = RuntimeError('private detail')
            else:
                instance.search_nearby_businesses.return_value = results.get(provider, [
                    business(provider, name=f'{provider} business', longitude=77.1 + len(provider) / 100),
                ])
            return instance

        settings_record = Mock()
        settings_record.business_providers = providers
        settings_record.hotel_provider = providers[0]
        with patch('hotels.services.providers.orchestrator.get_business_provider', side_effect=factory) as mocked:
            result = search_businesses_multi_provider(
                28.5, 77.1, 5000, 'hospitals', providers, settings_record
            )
        self.assertEqual(mocked.call_count, len(providers))
        return result

    def test_all_provider_combinations_are_called_once(self):
        combinations = [
            ['openstreetmap'], ['geoapify'], ['google'],
            ['openstreetmap', 'geoapify'], ['geoapify', 'google'],
            ['openstreetmap', 'geoapify', 'google'],
        ]
        for providers in combinations:
            with self.subTest(providers=providers):
                result = self.run_search(providers)
                self.assertEqual(result['providers'], providers)

    def test_each_partial_failure_preserves_success(self):
        cases = [
            (['openstreetmap', 'geoapify'], 'openstreetmap'),
            (['geoapify', 'openstreetmap'], 'geoapify'),
            (['google', 'geoapify'], 'google'),
        ]
        for providers, failed in cases:
            with self.subTest(failed=failed):
                result = self.run_search(providers, failures={failed})
                self.assertTrue(result['hotels'])
                self.assertEqual(result['provider_results'][failed]['status'], 'error')

    def test_all_failures_raise_frontend_compatible_error(self):
        with self.assertRaises(MultiProviderSearchError):
            self.run_search(['openstreetmap', 'geoapify'], failures={'openstreetmap', 'geoapify'})

    def test_domain_match_merges_complementary_fields_and_provenance(self):
        result = self.run_search(['openstreetmap', 'geoapify'], {
            'openstreetmap': [business('openstreetmap', phone='+1', website='https://www.acme.test/location')],
            'geoapify': [business('geoapify', website='http://acme.test')],
        })
        merged = result['hotels'][0]
        self.assertEqual((result['raw_result_count'], result['deduplicated_count']), (2, 1))
        self.assertEqual(merged['phone'], '+1')
        self.assertEqual(merged['website'], 'http://acme.test')
        self.assertEqual(merged['phone_source'], 'OpenStreetMap')
        self.assertEqual(merged['website_source'], 'Geoapify')
        self.assertEqual(merged['sources'], ['Geoapify', 'OpenStreetMap'])

    def test_similar_name_within_100_metres_merges(self):
        self.assertEqual(DEDUPLICATION_DISTANCE_KM, 0.1)
        result = self.run_search(['openstreetmap', 'geoapify'], {
            'openstreetmap': [business('openstreetmap', name='Apollo Hospital', latitude=28.5)],
            'geoapify': [business('geoapify', name='Apollo Hospitals', latitude=28.5005)],
        })
        self.assertEqual(result['deduplicated_count'], 1)

    def test_generic_or_branch_names_are_not_merged_when_distant(self):
        for name in ('Hospital', 'Acme Hospital'):
            with self.subTest(name=name):
                result = self.run_search(['openstreetmap', 'geoapify'], {
                    'openstreetmap': [business('openstreetmap', name=name, latitude=28.5, address='North Road')],
                    'geoapify': [business('geoapify', name=name, latitude=28.52, address='South Road')],
                })
                self.assertEqual(result['deduplicated_count'], 2)

    def test_conflicts_use_google_then_geoapify_then_osm(self):
        result = self.run_search(['openstreetmap', 'geoapify', 'google'], {
            'openstreetmap': [business('openstreetmap', phone='osm', website='acme.test')],
            'geoapify': [business('geoapify', phone='geo', email='geo@acme.test', website='acme.test')],
            'google': [business('google', phone='google', website='acme.test')],
        })
        merged = result['hotels'][0]
        self.assertEqual(merged['phone'], 'google')
        self.assertEqual(merged['phone_source'], 'Google Places')
        self.assertEqual(merged['email'], 'geo@acme.test')


class MultiProviderNearbyAPITests(TestCase):
    @patch('hotels.views.search_businesses_multi_provider')
    def test_explicit_providers_extend_response(self, search):
        search.return_value = {
            'hotels': [], 'providers': ['openstreetmap', 'geoapify'],
            'provider_results': {'openstreetmap': {'status': 'success', 'count': 0},
                                 'geoapify': {'status': 'success', 'count': 0}},
            'raw_result_count': 0, 'deduplicated_count': 0,
        }
        response = self.client.get('/api/hotels/nearby/', [
            ('lat', 28.5), ('lng', 77.1), ('radius', 5000),
            ('providers', 'openstreetmap'), ('providers', 'geoapify'),
        ])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['providers'], ['openstreetmap', 'geoapify'])
