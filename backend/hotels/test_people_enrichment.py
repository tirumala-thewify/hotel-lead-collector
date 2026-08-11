from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase
from hotels.models import ProviderSettings

from hotels.services.people_enrichment.apollo import (
    ApolloPeopleEnrichmentProvider,
    ORGANIZATION_SEARCH_URL,
    _request_json,
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
        self.assertEqual(result, {
            'hotel_name': 'Roseate House', 'contacts': [], 'status': 'NOT_FOUND'
        })

    @patch('hotels.services.people_enrichment.apollo.requests.post')
    def test_apollo_http_error(self, mock_post):
        mock_post.return_value = Mock(status_code=429)
        with self.assertRaisesMessage(PeopleEnrichmentError, 'HTTP 429'):
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
        self.assertEqual(result['status'], 'FOUND')
        self.assertEqual(len(result['contacts']), 3)


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

    @patch('hotels.views.search_decision_makers')
    def test_api_endpoint_not_found(self, mock_search):
        mock_search.return_value = {
            'hotel_name': 'Roseate House', 'contacts': [], 'status': 'NOT_FOUND'
        }
        response = self.client.post(self.url, {'name': 'Roseate House'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['contacts'], [])
