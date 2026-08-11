from unittest.mock import patch

from rest_framework.test import APITestCase

from hotels.services.enrichment.base import EnrichmentError


class BulkHotelEnrichmentAPITests(APITestCase):
    url = '/api/hotels/enrich/bulk/'

    def _post(self, hotels):
        return self.client.post(self.url, {'hotels': hotels}, format='json')

    def test_empty_payload(self):
        self.assertEqual(self._post([]).status_code, 400)

    def test_maximum_ten_hotels(self):
        self.assertEqual(self._post([{'name': f'Hotel {i}'} for i in range(11)]).status_code, 400)

    def test_invalid_hotel_payload(self):
        self.assertEqual(self._post([{'website': 'not-a-url'}]).status_code, 400)

    @patch('hotels.services.enrichment.bulk.enrich_hotel_from_website')
    def test_single_hotel_improvement_tracks_sources(self, mock_enrich):
        mock_enrich.return_value = {
            'website': 'https://hotel.example/', 'phone': '+91 1111111111',
            'email': None, 'address': None, 'brand': None,
            'sources': {'website': 'Wikidata Q1', 'phone': 'https://hotel.example/contact'},
            'website_confidence': 'HIGH',
        }
        data = self._post([{'name': 'Example Hotel', 'source': 'OpenStreetMap'}]).json()
        result = data['results'][0]
        self.assertEqual(result['status'], 'FOUND')
        self.assertEqual(result['fields_added'], ['phone', 'website'])
        self.assertEqual(result['sources']['phone'], 'https://hotel.example/contact')
        self.assertEqual(result['website_confidence'], 'HIGH')

    @patch('hotels.services.enrichment.bulk.enrich_hotel_from_website')
    def test_existing_stronger_values_and_brand_are_preserved(self, mock_enrich):
        mock_enrich.return_value = {
            'website': 'https://other.example/', 'phone': '+91 9999999999',
            'email': 'new@hotel.example', 'address': 'Partial', 'brand': 'Other',
            'sources': {'email': 'https://hotel.example/contact'},
        }
        result = self._post([{
            'name': 'Hotel', 'address': 'Complete OSM Address, Delhi',
            'phone': '+91 1111111111', 'website': 'https://hotel.example/',
            'brand': 'Existing Brand', 'source': 'OpenStreetMap',
        }]).json()['results'][0]
        self.assertEqual(result['hotel']['address'], 'Complete OSM Address, Delhi')
        self.assertEqual(result['hotel']['phone'], '+91 1111111111')
        self.assertEqual(result['hotel']['website'], 'https://hotel.example/')
        self.assertEqual(result['hotel']['brand'], 'Existing Brand')
        self.assertEqual(result['hotel']['email'], 'new@hotel.example')
        self.assertEqual(result['sources']['address'], 'OpenStreetMap')

    @patch('hotels.services.enrichment.bulk.enrich_hotel_from_website')
    def test_multiple_improvements_and_summary(self, mock_enrich):
        mock_enrich.side_effect = [
            {'phone': '+1', 'sources': {'phone': 'https://one.example/'}, 'website_confidence': 'HIGH'},
            {'email': 'info@two.example', 'sources': {'email': 'https://two.example/'}, 'website_confidence': 'HIGH'},
        ]
        data = self._post([{'name': 'One'}, {'name': 'Two'}]).json()
        self.assertEqual([result['status'] for result in data['results']], ['PARTIAL', 'PARTIAL'])
        self.assertEqual(data['summary']['improved'], 2)
        self.assertEqual(data['summary']['fields_added']['phone'], 1)
        self.assertEqual(data['summary']['fields_added']['email'], 1)

    @patch('hotels.services.enrichment.bulk.enrich_hotel_from_website')
    def test_one_failure_does_not_stop_batch(self, mock_enrich):
        mock_enrich.side_effect = [
            EnrichmentError('private detail'),
            {'phone': '+1', 'sources': {'phone': 'https://two.example/'}, 'website_confidence': 'HIGH'},
        ]
        response = self._post([{'name': 'One'}, {'name': 'Two'}])
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['status'] for item in response.json()['results']], ['ERROR', 'PARTIAL'])
        self.assertNotContains(response, 'private detail')
        self.assertEqual(response.json()['summary']['errors'], 1)
        self.assertEqual(mock_enrich.call_count, 2)
