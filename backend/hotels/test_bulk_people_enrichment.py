from unittest.mock import patch

from rest_framework.test import APITestCase

from hotels.models import ProviderSettings
from hotels.services.people_enrichment.base import PeopleEnrichmentError


class BulkManagerEnrichmentAPITests(APITestCase):
    url = '/api/hotels/enrich-managers/bulk/'

    def setUp(self):
        settings = ProviderSettings.load()
        settings.apollo_enabled = True
        settings.set_apollo_api_key('test-key')
        settings.save()

    def _post(self, hotels):
        return self.client.post(self.url, {'hotels': hotels}, format='json')

    def test_apollo_disabled(self):
        settings = ProviderSettings.load()
        settings.apollo_enabled = False
        settings.save()
        response = self._post([{'name': 'Roseate House'}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'DISABLED')

    def test_apollo_enabled_without_key(self):
        settings = ProviderSettings.load()
        settings.set_apollo_api_key('')
        settings.save()
        response = self._post([{'name': 'Roseate House'}])
        self.assertEqual(response.status_code, 503)
        self.assertIn('no API key', response.json()['message'])

    def test_empty_hotels_payload(self):
        self.assertEqual(self._post([]).status_code, 400)

    def test_more_than_ten_hotels_is_rejected(self):
        response = self._post([{'name': f'Hotel {index}'} for index in range(11)])
        self.assertEqual(response.status_code, 400)

    @patch('hotels.services.people_enrichment.bulk.search_decision_makers')
    def test_one_hotel_success_and_normalized_manager_data(self, mock_search):
        mock_search.return_value = {
            'status': 'FOUND',
            'contacts': [{
                'name': 'A Person', 'title': 'General Manager',
                'department': 'General Management', 'email': None, 'phone': None,
                'linkedin_url': 'https://linkedin.com/in/a-person', 'source': 'Apollo',
                'company': 'Ignored Company', 'verification_status': 'FOUND',
            }],
        }
        data = self._post([{'name': 'Roseate House'}]).json()
        self.assertEqual(data['results'][0], {
            'hotel_name': 'Roseate House', 'status': 'FOUND',
            'contacts': [{
                'name': 'A Person', 'title': 'General Manager',
                'department': 'General Management', 'email': None, 'phone': None,
                'linkedin_url': 'https://linkedin.com/in/a-person', 'source': 'Apollo',
            }],
        })
        self.assertEqual(data['summary'], {
            'requested': 1, 'processed': 1, 'found': 1, 'not_found': 0, 'errors': 0,
        })

    @patch('hotels.services.people_enrichment.bulk.search_decision_makers')
    def test_multiple_success_includes_gm_marketing_and_it(self, mock_search):
        contacts = [
            {'name': 'GM', 'title': 'General Manager', 'department': 'General Management'},
            {'name': 'M', 'title': 'Marketing Manager', 'department': 'Marketing'},
            {'name': 'IT', 'title': 'IT Manager', 'department': 'Information Technology'},
        ]
        mock_search.return_value = {'status': 'FOUND', 'contacts': contacts}
        data = self._post([{'name': 'Hotel One'}, {'name': 'Hotel Two'}]).json()
        self.assertEqual(len(data['results']), 2)
        self.assertEqual(
            [contact['department'] for contact in data['results'][0]['contacts']],
            ['General Management', 'Marketing', 'Information Technology'],
        )
        self.assertEqual(mock_search.call_count, 2)

    @patch('hotels.services.people_enrichment.bulk.search_decision_makers')
    def test_organization_not_found(self, mock_search):
        mock_search.return_value = {'status': 'NOT_FOUND', 'contacts': []}
        data = self._post([{'name': 'Unknown Hotel'}]).json()
        self.assertEqual(data['results'][0]['status'], 'NOT_FOUND')
        self.assertEqual(data['summary']['not_found'], 1)

    @patch('hotels.services.people_enrichment.bulk.search_decision_makers')
    def test_max_three_contacts_and_one_per_department(self, mock_search):
        mock_search.return_value = {'status': 'FOUND', 'contacts': [
            {'name': 'GM 1', 'department': 'General Management'},
            {'name': 'GM 2', 'department': 'General Management'},
            {'name': 'M', 'department': 'Marketing'},
            {'name': 'IT', 'department': 'Information Technology'},
            {'name': 'Sales', 'department': 'Sales / Commercial'},
        ]}
        contacts = self._post([{'name': 'Hotel'}]).json()['results'][0]['contacts']
        self.assertEqual(len(contacts), 3)
        self.assertEqual(len({contact['department'] for contact in contacts}), 3)

    @patch('hotels.services.people_enrichment.bulk.search_decision_makers')
    def test_one_failure_does_not_fail_batch_and_summary_counts(self, mock_search):
        mock_search.side_effect = [
            {'status': 'FOUND', 'contacts': [
                {'name': 'GM', 'title': 'General Manager', 'department': 'General Management'},
            ]},
            PeopleEnrichmentError('sensitive provider detail'),
            {'status': 'NOT_FOUND', 'contacts': []},
        ]
        response = self._post([
            {'name': 'Hotel One'}, {'name': 'Hotel Two'}, {'name': 'Hotel Three'},
        ])
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual([item['status'] for item in data['results']], [
            'FOUND', 'ERROR', 'NOT_FOUND',
        ])
        self.assertNotContains(response, 'sensitive provider detail')
        self.assertEqual(data['summary'], {
            'requested': 3, 'processed': 3, 'found': 1, 'not_found': 1, 'errors': 1,
        })
