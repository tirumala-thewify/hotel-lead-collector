from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase
from hotels.models import ProviderSettings

from hotels.services.people_enrichment.apollo import (
    ApolloPeopleEnrichmentProvider,
    ORGANIZATION_SEARCH_URL,
    _request_json,
    search_decision_makers,
)
from hotels.services.people_enrichment.base import (
    PeopleEnrichmentConfigurationError,
    PeopleEnrichmentError,
)


class ApolloPeopleEnrichmentTests(SimpleTestCase):
    def setUp(self):
        self.provider = ApolloPeopleEnrichmentProvider(api_key='test-key')

    @override_settings(APOLLO_API_KEY='')
    def test_missing_api_key(self):
        with self.assertRaisesMessage(
            PeopleEnrichmentConfigurationError, 'APOLLO_API_KEY is not configured.'
        ):
            ApolloPeopleEnrichmentProvider()

    @patch('hotels.services.people_enrichment.apollo._request_json')
    def test_organization_match_prefers_exact_domain(self, mock_request):
        mock_request.return_value = {'organizations': [
            {'id': 'wrong', 'name': 'Roseate', 'primary_domain': 'other.example'},
            {'id': 'right', 'name': 'Roseate Hotels', 'primary_domain': 'roseatehotels.com'},
        ]}
        organization = self.provider.match_organization(
            'Roseate House', 'https://www.roseatehotels.com/property/'
        )
        self.assertEqual(organization['id'], 'right')
        params = mock_request.call_args.args[2]
        self.assertEqual(params['q_organization_domains_list[]'], 'roseatehotels.com')
        self.assertNotIn('q_organization_name', params)

    def test_domain_extraction_removes_path_and_accepts_bare_domain(self):
        from hotels.services.people_enrichment.apollo import _domain

        self.assertEqual(_domain('https://www.example.com/location/page'), 'example.com')
        self.assertEqual(_domain('example.com'), 'example.com')
        self.assertIsNone(_domain('not a domain/path'))

    @patch('hotels.services.people_enrichment.apollo._request_json')
    def test_organization_name_and_location_fallback(self, mock_request):
        mock_request.return_value = {'organizations': [
            {'id': 'right', 'name': 'ABC School'},
        ]}
        organization = self.provider.match_organization({
            'name': 'ABC School', 'address': 'Hyderabad',
        })
        self.assertEqual(organization['id'], 'right')
        params = mock_request.call_args.args[2]
        self.assertEqual(params['q_organization_name'], 'ABC School')
        self.assertEqual(params['organization_locations[]'], 'Hyderabad')

    @patch('hotels.services.people_enrichment.apollo._request_json')
    def test_no_organization_match(self, mock_request):
        mock_request.return_value = {'organizations': [
            {'id': 'wrong', 'name': 'Unrelated', 'primary_domain': 'unrelated.example'},
        ]}
        self.assertIsNone(self.provider.match_organization(
            'Roseate House', 'https://roseatehotels.com/'
        ))

    def test_general_manager_found(self):
        people = self.provider._select_people([
            {'id': 'gm', 'name': 'A Person', 'title': 'General Manager'},
        ])
        self.assertEqual(people[0]['id'], 'gm')

    def test_marketing_contact_found(self):
        contact = self.provider._normalize_contact(
            {'name': 'B Person', 'title': 'Director of Marketing'}, {}, 'Roseate Hotels'
        )
        self.assertEqual(contact['department'], 'Marketing')

    def test_it_contact_found(self):
        contact = self.provider._normalize_contact(
            {'name': 'C Person', 'title': 'Information Technology Manager'}, {}, 'Roseate Hotels'
        )
        self.assertEqual(contact['department'], 'Information Technology')

    def test_contact_without_email(self):
        contact = self.provider._normalize_contact(
            {'name': 'A Person', 'title': 'General Manager'}, {}, 'Roseate Hotels'
        )
        self.assertIsNone(contact['email'])

    def test_contact_without_phone(self):
        contact = self.provider._normalize_contact(
            {'name': 'A Person', 'title': 'General Manager', 'phone_numbers': []},
            {}, 'Roseate Hotels'
        )
        self.assertIsNone(contact['phone'])

    @patch.object(ApolloPeopleEnrichmentProvider, 'match_organization')
    def test_no_people_found(self, mock_organization):
        mock_organization.return_value = {'id': 'org-1', 'name': 'Roseate Hotels'}
        with patch.object(self.provider, 'search_people', return_value=[]):
            result = self.provider.search_decision_makers('Roseate House')
        self.assertEqual(result['hotel_name'], 'Roseate House')
        self.assertEqual(result['business_name'], 'Roseate House')
        self.assertEqual(result['category'], 'hotels_resorts')
        self.assertEqual(result['contacts'], [])
        self.assertEqual(result['status'], 'NOT_FOUND')

    @patch('hotels.services.people_enrichment.apollo.requests.post')
    def test_apollo_http_error(self, mock_post):
        mock_post.return_value = Mock(status_code=429)
        with self.assertRaisesMessage(PeopleEnrichmentError, 'quota or rate limit'):
            _request_json(ORGANIZATION_SEARCH_URL, 'key', {})

    @patch('hotels.services.people_enrichment.apollo.requests.post', side_effect=requests.Timeout)
    def test_apollo_timeout(self, mock_post):
        with self.assertRaisesMessage(PeopleEnrichmentError, 'timed out'):
            _request_json(ORGANIZATION_SEARCH_URL, 'key', {})

    @patch('hotels.services.people_enrichment.apollo.requests.post')
    def test_malformed_response(self, mock_post):
        response = Mock(status_code=200)
        response.json.return_value = []
        mock_post.return_value = response
        with self.assertRaisesMessage(PeopleEnrichmentError, 'malformed'):
            _request_json(ORGANIZATION_SEARCH_URL, 'key', {})

    @patch.object(ApolloPeopleEnrichmentProvider, 'match_organization')
    def test_full_flow_normalizes_small_role_set(self, mock_organization):
        mock_organization.return_value = {'id': 'org-1', 'name': 'Roseate Hotels'}
        candidates = [
            {'id': '1', 'name': 'GM', 'title': 'General Manager'},
            {'id': '2', 'name': 'Marketing', 'title': 'Marketing Manager'},
            {'id': '3', 'name': 'IT', 'title': 'IT Manager'},
            {'id': '4', 'name': 'Junior', 'title': 'Marketing Executive'},
        ]
        with patch.object(self.provider, 'search_people', return_value=candidates), \
             patch.object(self.provider, 'enrich_person', side_effect=lambda person, *args: person):
            result = self.provider.search_decision_makers('Roseate House')
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertEqual(len(result['contacts']), 3)

    def test_title_matching_is_punctuation_tolerant(self):
        contact = self.provider._normalize_contact(
            {'name': 'IT Person', 'title': 'Director, Information Technology'},
            {}, 'ABC Hospital', 'hospitals',
        )
        self.assertEqual(contact['role_group'], 'IT')

    def test_unrelated_manager_title_is_rejected(self):
        self.assertIsNone(self.provider._normalize_contact(
            {'name': 'Person', 'title': 'Account Manager'},
            {}, 'ABC Restaurant', 'restaurants',
        ))

    def test_selection_prioritizes_titles_and_one_per_role_group(self):
        selected = self.provider._select_people([
            {'id': 'manager', 'title': 'Restaurant Manager'},
            {'id': 'owner', 'title': 'Owner'},
            {'id': 'operations', 'title': 'Operations Manager'},
            {'id': 'marketing', 'title': 'Marketing Manager'},
            {'id': 'extra', 'title': 'Head of Marketing'},
        ], 'restaurants')
        self.assertEqual([person['id'] for person in selected], [
            'owner', 'operations', 'marketing',
        ])

    @patch('hotels.services.people_enrichment.apollo._request_json')
    def test_people_search_is_category_scoped(self, mock_request):
        mock_request.return_value = {'people': []}
        self.provider.search_people('org-1', 'schools')
        params = mock_request.call_args.args[2]
        self.assertIn('Principal', params['person_titles[]'])
        self.assertNotIn('Restaurant Manager', params['person_titles[]'])
        self.assertIn('director', params['person_seniorities[]'])

    @patch('hotels.services.people_enrichment.apollo._request_json')
    def test_person_enrichment_disables_personal_email_and_phone_reveal(self, mock_request):
        mock_request.return_value = {'person': {'id': 'person-1'}}
        self.provider.enrich_person(
            {'id': 'person-1', 'name': 'Person'}, 'ABC School', 'abc.edu'
        )
        params = mock_request.call_args.args[2]
        self.assertEqual(params['reveal_personal_emails'], 'false')
        self.assertEqual(params['reveal_phone_number'], 'false')

    @patch.object(ApolloPeopleEnrichmentProvider, 'match_organization')
    def test_identity_only_contact_is_partial_and_values_are_not_guessed(self, mock_org):
        mock_org.return_value = {'id': 'org-1', 'name': 'ABC School'}
        candidate = {'id': 'person-1', 'name': 'A Person', 'title': 'Principal'}
        with patch.object(self.provider, 'search_people', return_value=[candidate]), \
             patch.object(self.provider, 'enrich_person', return_value=candidate):
            result = self.provider.search_decision_makers(
                {'name': 'ABC School'}, 'schools'
            )
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertIsNone(result['contacts'][0]['business_email'])
        self.assertIsNone(result['contacts'][0]['phone'])

    @patch.object(ApolloPeopleEnrichmentProvider, 'search_decision_makers')
    def test_legacy_function_arguments_default_to_hotels(self, mock_search):
        mock_search.return_value = {'status': 'NOT_FOUND', 'contacts': []}
        search_decision_makers(
            hotel_name='Legacy Hotel', website='https://hotel.example',
            location='Delhi', api_key='key',
        )
        mock_search.assert_called_once_with({
            'name': 'Legacy Hotel',
            'website': 'https://hotel.example',
            'address': 'Delhi',
        }, 'hotels_resorts')

    @patch('hotels.services.people_enrichment.apollo.requests.post')
    def test_api_key_is_header_only(self, mock_post):
        response = Mock(status_code=200)
        response.json.return_value = {}
        mock_post.return_value = response
        _request_json(ORGANIZATION_SEARCH_URL, 'secret-key', {'page': 1})
        call = mock_post.call_args
        self.assertNotIn('secret-key', call.args[0])
        self.assertNotIn('api_key', call.kwargs['params'])
        self.assertEqual(call.kwargs['headers']['X-Api-Key'], 'secret-key')

    @patch('hotels.services.people_enrichment.apollo.requests.post')
    def test_permission_errors_are_clean(self, mock_post):
        for status in (401, 403):
            with self.subTest(status=status):
                mock_post.return_value = Mock(status_code=status)
                with self.assertRaisesMessage(PeopleEnrichmentError, 'access is not available'):
                    _request_json(ORGANIZATION_SEARCH_URL, 'key', {})

    @patch('hotels.services.people_enrichment.apollo.requests.post')
    def test_server_error_is_clean(self, mock_post):
        mock_post.return_value = Mock(status_code=500)
        with self.assertRaisesMessage(PeopleEnrichmentError, 'temporarily unavailable'):
            _request_json(ORGANIZATION_SEARCH_URL, 'key', {})


class ManagerEnrichmentAPITests(APITestCase):
    url = '/api/hotels/enrich-managers/'

    def setUp(self):
        provider_settings = ProviderSettings.load()
        provider_settings.apollo_enabled = True
        provider_settings.set_apollo_api_key('test-key')
        provider_settings.save()

    @patch('hotels.views.search_decision_makers')
    def test_api_endpoint_success(self, mock_search):
        mock_search.return_value = {
            'hotel_name': 'Roseate House',
            'contacts': [{'name': 'A Person', 'title': 'General Manager'}],
            'status': 'FOUND',
        }
        response = self.client.post(self.url, {
            'name': 'Roseate House',
            'website': 'https://www.roseatehotels.com/newdelhi/roseatehouse/',
            'brand': 'Roseate Hotels',
            'location': 'New Delhi',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'FOUND')
        self.assertEqual(mock_search.call_args.kwargs['category'], 'hotels_resorts')

    @patch('hotels.views.search_decision_makers')
    def test_api_accepts_generic_business_category(self, mock_search):
        mock_search.return_value = {
            'business_name': 'ABC School', 'category': 'schools',
            'contacts': [], 'status': 'NOT_FOUND',
        }
        response = self.client.post(self.url, {
            'name': 'ABC School', 'address': 'Hyderabad', 'category': 'schools',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_search.call_args.kwargs['category'], 'schools')

    @patch('hotels.views.search_decision_makers')
    def test_api_endpoint_not_found(self, mock_search):
        mock_search.return_value = {
            'hotel_name': 'Roseate House', 'contacts': [], 'status': 'NOT_FOUND'
        }
        response = self.client.post(self.url, {'name': 'Roseate House'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['contacts'], [])
