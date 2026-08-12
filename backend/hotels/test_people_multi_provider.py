from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from hotels.models import ProviderSettings
from hotels.provider_settings import get_people_providers
from hotels.services.people_enrichment.base import (
    PeopleEnrichmentConfigurationError, PeopleEnrichmentError,
)
from hotels.services.people_enrichment.orchestrator import (
    search_decision_makers_multi_provider,
)
from hotels.services.people_enrichment.zoominfo import ZoomInfoPeopleEnrichmentProvider


def contact(source, name='Jane Doe', title='IT Director', **values):
    return {
        'provider_person_id': values.pop('provider_person_id', f'{source}-1'),
        'name': name, 'title': title, 'role_group': values.pop('role_group', 'IT Leadership'),
        'organization_name': values.pop('organization_name', 'Acme'),
        'business_email': None, 'phone': None, 'linkedin_url': None,
        'source': source, **values,
    }


@override_settings(APOLLO_API_KEY='', ZOOMINFO_API_KEY='')
class PeopleProviderSettingsTests(APITestCase):
    url = '/api/settings/providers/'

    def test_none_apollo_zoominfo_and_both(self):
        self.assertEqual(self.client.put(self.url, {'people_providers': []}, format='json').status_code, 200)
        cases = [
            (['apollo'], {'apollo_api_key': 'a'}),
            (['zoominfo'], {'zoominfo_api_key': 'z'}),
            (['apollo', 'zoominfo'], {'apollo_api_key': 'a', 'zoominfo_api_key': 'z'}),
        ]
        for providers, keys in cases:
            with self.subTest(providers=providers):
                response = self.client.put(
                    self.url, {'people_providers': providers, **keys}, format='json'
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['people_providers'], providers)

    def test_unconfigured_selected_provider_is_rejected(self):
        for provider in ('apollo', 'zoominfo'):
            ProviderSettings.objects.all().delete()
            with self.subTest(provider=provider):
                response = self.client.put(
                    self.url, {'people_providers': [provider]}, format='json'
                )
                self.assertEqual(response.status_code, 400)

    def test_zoominfo_secret_encrypted_preserved_and_hidden(self):
        self.client.put(self.url, {'zoominfo_api_key': 'zoom-secret'}, format='json')
        self.client.put(self.url, {'zoominfo_api_key': ''}, format='json')
        settings = ProviderSettings.load()
        self.assertEqual(settings.get_zoominfo_api_key(), 'zoom-secret')
        self.assertNotEqual(settings.zoominfo_api_key_encrypted, 'zoom-secret')
        self.assertNotIn('zoom-secret', str(self.client.get(self.url).json()))

    def test_legacy_apollo_enabled_fallback(self):
        settings = ProviderSettings.load()
        settings.apollo_enabled = True
        settings.people_providers = []
        settings.save()
        self.assertEqual(get_people_providers(settings), ['apollo'])


class ZoomInfoAdapterTests(SimpleTestCase):
    def setUp(self):
        self.transport = Mock()
        self.provider = ZoomInfoPeopleEnrichmentProvider('key', self.transport)
        self.business = {'name': 'Acme', 'website': 'https://acme.test'}
        self.transport.search_organizations.return_value = [
            {'id': 'org', 'name': 'Acme', 'domain': 'acme.test'}
        ]

    @override_settings(ZOOMINFO_API_KEY='')
    def test_missing_credential(self):
        with self.assertRaises(PeopleEnrichmentConfigurationError):
            ZoomInfoPeopleEnrichmentProvider()

    def test_organization_match_and_not_found(self):
        self.assertEqual(self.provider.match_organization(self.business)['id'], 'org')
        self.transport.search_organizations.return_value = []
        self.assertIsNone(self.provider.match_organization(self.business))

    def test_primary_title_families_normalize_without_guesses(self):
        titles = ['IT Director', 'IT Manager', 'General Manager', 'CIO', 'CTO', 'Director of Operations']
        self.transport.search_people.return_value = [
            {'id': str(index), 'name': f'Person {index}', 'title': title}
            for index, title in enumerate(titles)
        ]
        result = self.provider.search_decision_makers(self.business, 'hospitals')
        self.assertEqual(len(result['contacts']), 3)
        self.assertIsNone(result['contacts'][0]['business_email'])
        self.assertIsNone(result['contacts'][0]['phone'])
        self.assertFalse(self.transport.search_people.call_args.kwargs['reveal_contacts'])

    def test_malformed_transport_response(self):
        self.transport.search_people.return_value = {'people': []}
        with self.assertRaisesMessage(PeopleEnrichmentError, 'malformed people'):
            self.provider.search_decision_makers(self.business)

    def test_clean_transport_errors_propagate(self):
        for message in ('401', '403', '429', '5xx', 'timeout'):
            with self.subTest(message=message):
                self.transport.search_organizations.side_effect = PeopleEnrichmentError(message)
                with self.assertRaisesMessage(PeopleEnrichmentError, message):
                    self.provider.match_organization(self.business)


class PeopleOrchestratorTests(SimpleTestCase):
    def search(self, providers, results=None, failures=()):
        results = results or {}
        settings = Mock(people_providers=providers, apollo_enabled='apollo' in providers)

        def factory(provider, _settings):
            adapter = Mock()
            if provider in failures:
                adapter.search_decision_makers.side_effect = PeopleEnrichmentError('private')
            else:
                adapter.search_decision_makers.return_value = {
                    'contacts': results.get(provider, [contact(provider.title())]), 'status': 'FOUND'
                }
            return adapter

        with patch('hotels.services.people_enrichment.orchestrator.get_people_provider', side_effect=factory) as mocked:
            output = search_decision_makers_multi_provider(
                {'name': 'Acme'}, 'hospitals', providers, settings
            )
        self.assertEqual(mocked.call_count, len(providers))
        return output

    def test_apollo_zoominfo_and_both(self):
        for providers in (['apollo'], ['zoominfo'], ['apollo', 'zoominfo']):
            with self.subTest(providers=providers):
                self.assertEqual(self.search(providers)['providers'], providers)

    def test_partial_and_total_failures(self):
        for failed in ('apollo', 'zoominfo'):
            result = self.search(['apollo', 'zoominfo'], failures={failed})
            self.assertNotEqual(result['status'], 'ERROR')
            self.assertEqual(result['provider_results'][failed]['status'], 'error')
        self.assertEqual(self.search(
            ['apollo', 'zoominfo'], failures={'apollo', 'zoominfo'}
        )['status'], 'ERROR')

    def test_same_person_merges_complementary_fields_and_sources(self):
        result = self.search(['apollo', 'zoominfo'], {
            'apollo': [contact('Apollo', business_email='jane@acme.test')],
            'zoominfo': [contact('ZoomInfo', phone='+1', provider_person_id='z')],
        })
        merged = result['contacts'][0]
        self.assertEqual(len(result['contacts']), 1)
        self.assertEqual(merged['business_email_source'], 'Apollo')
        self.assertEqual(merged['phone_source'], 'ZoomInfo')
        self.assertEqual(merged['sources'], ['Apollo', 'ZoomInfo'])

    def test_different_people_remain_and_output_is_capped_at_three(self):
        result = self.search(['apollo', 'zoominfo'], {
            'apollo': [contact('Apollo', name=f'Person {i}', title='IT Director', provider_person_id=f'a{i}') for i in range(3)],
            'zoominfo': [contact('ZoomInfo', name=f'Other {i}', title='General Manager', provider_person_id=f'z{i}') for i in range(3)],
        })
        self.assertEqual(len(result['contacts']), 3)

    def test_email_or_linkedin_are_strong_identifiers(self):
        for field, value in (('business_email', 'same@acme.test'), ('linkedin_url', 'https://linkedin.com/in/same')):
            with self.subTest(field=field):
                result = self.search(['apollo', 'zoominfo'], {
                    'apollo': [contact('Apollo', name='Jane A', **{field: value})],
                    'zoominfo': [contact('ZoomInfo', name='Jane B', **{field: value})],
                })
                self.assertEqual(len(result['contacts']), 1)


class PeopleMultiProviderAPITests(APITestCase):
    def setUp(self):
        settings = ProviderSettings.load()
        settings.people_providers = ['apollo', 'zoominfo']
        settings.set_apollo_api_key('a')
        settings.set_zoominfo_api_key('z')
        settings.apollo_enabled = True
        settings.save()

    @patch('hotels.views.search_decision_makers_multi_provider')
    def test_single_endpoint_forwards_batch_provider_selection(self, search):
        search.return_value = {'business_name': 'Acme', 'status': 'NOT_FOUND', 'contacts': []}
        response = self.client.post('/api/hotels/enrich-managers/', {
            'name': 'Acme', 'providers': ['apollo', 'zoominfo'],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(search.call_args.kwargs['providers'], ['apollo', 'zoominfo'])

    @patch('hotels.views.enrich_managers_multi_provider_bulk')
    def test_bulk_accepts_businesses_alias_and_batch_providers(self, bulk):
        bulk.return_value = {'results': [], 'summary': {}}
        response = self.client.post('/api/hotels/enrich-managers/bulk/', {
            'businesses': [{'name': 'Acme'}], 'providers': ['zoominfo'],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(bulk.call_args.args[1], ['zoominfo'])
