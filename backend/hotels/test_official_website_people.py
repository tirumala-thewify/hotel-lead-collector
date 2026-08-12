from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APITestCase

from hotels.models import ProviderSettings
from hotels.services.enrichment.base import EnrichmentError
from hotels.services.people_enrichment.official_website import (
    OfficialWebsitePeopleEnrichmentProvider,
    extract_official_website_contacts,
)
from hotels.services.people_enrichment.orchestrator import (
    search_decision_makers_multi_provider,
)


BUSINESS = {
    'name': 'Example Hotel', 'website': 'https://hotel.example/',
    'source': 'Browser Search',
}


class OfficialWebsitePeopleParserTests(SimpleTestCase):
    def contacts(self, html, url='https://hotel.example/team'):
        return extract_official_website_contacts(html, url, 'hotel.example')

    def test_name_then_general_manager(self):
        contact = self.contacts('<p>John Smith — General Manager</p>')[0]
        self.assertEqual(contact['name'], 'John Smith')
        self.assertEqual(contact['role_group'], 'general_manager')

    def test_general_manager_then_name(self):
        contact = self.contacts('<p>General Manager: John Smith</p>')[0]
        self.assertEqual(contact['name'], 'John Smith')
        self.assertEqual(contact['title'], 'General Manager')

    def test_general_manager_without_contacts_does_not_guess(self):
        contact = self.contacts('<p>Meet our General Manager, John Smith</p>')[0]
        self.assertIsNone(contact['business_email'])
        self.assertIsNone(contact['phone'])

    def test_general_manager_with_associated_business_email(self):
        contact = self.contacts(
            '<p>John Smith — General Manager '
            '<a href="mailto:john.smith@hotel.example">Email</a></p>'
        )[0]
        self.assertEqual(contact['business_email'], 'john.smith@hotel.example')
        self.assertEqual(contact['business_email_source'], 'https://hotel.example/team')

    def test_director_of_sales_and_sales_manager(self):
        contacts = self.contacts(
            '<p>Jane Doe — Director of Sales</p>'
            '<p>Rahul Kumar — Sales Manager</p>'
        )
        self.assertEqual([item['title'] for item in contacts], [
            'Director of Sales', 'Sales Manager',
        ])

    def test_generic_sales_team_email_and_phone(self):
        contact = self.contacts(
            '<p>Sales Team <a href="mailto:sales@hotel.example">Email</a> '
            '<a href="tel:+911122223333">Call</a></p>',
            'https://hotel.example/sales',
        )[0]
        self.assertIsNone(contact['name'])
        self.assertEqual(contact['title'], 'Sales Team')
        self.assertEqual(contact['business_email'], 'sales@hotel.example')
        self.assertEqual(contact['phone'], '+911122223333')

    def test_footer_sales_email_is_not_assigned_to_general_manager(self):
        contacts = self.contacts(
            '<article><p>John Smith — General Manager</p></article>'
            '<footer><p><a href="mailto:sales@hotel.example">Sales</a></p></footer>'
        )
        gm = next(item for item in contacts if item['role_group'] == 'general_manager')
        self.assertIsNone(gm['business_email'])

    def test_legal_sales_conditions_are_ignored(self):
        contacts = self.contacts(
            '<p>Sales conditions <a href="mailto:sales@hotel.example">Email</a></p>',
            'https://hotel.example/legal/internet-sales-conditions',
        )
        self.assertEqual(contacts, [])

    def test_source_url_and_confidence_are_preserved(self):
        contact = self.contacts('<p>John Smith — General Manager</p>')[0]
        self.assertEqual(contact['source_url'], 'https://hotel.example/team')
        self.assertEqual(contact['confidence'], 'HIGH')
        self.assertEqual(contact['source'], 'Official Website')
        self.assertIsNone(contact['linkedin_url'])

    def test_target_technology_operations_and_executive_roles(self):
        html = '''
          <p>Alice Brown - IT Director</p>
          <p>Brian Green - IT Infrastructure Manager</p>
          <p>Carla White - Chief Information Officer</p>
          <p>David Black - Director of Operations</p>
          <p>Elena Stone - Hotel General Manager</p>
        '''
        contacts = self.contacts(html)
        self.assertEqual(
            {contact['role_group'] for contact in contacts},
            {'it_leadership', 'it_management', 'executive', 'operations', 'general_manager'},
        )
        self.assertTrue(all(contact['source_url'] for contact in contacts))

    def test_unrelated_titles_are_ignored(self):
        self.assertEqual(self.contacts('<p>Jane Doe - Restaurant Manager</p>'), [])


@patch('hotels.services.people_enrichment.official_website._fetch_html')
class OfficialWebsitePeopleProviderTests(SimpleTestCase):
    def setUp(self):
        self.provider = OfficialWebsitePeopleEnrichmentProvider()

    def test_multiple_people_are_prioritized(self, fetch):
        fetch.return_value = ('https://hotel.example/', '''
          <p>Alice Brown — Sales Executive</p>
          <p>John Smith — General Manager</p>
          <p>Jane Doe — Director of Sales</p>
          <p>Rahul Kumar — Sales Manager</p>
        ''')
        result = self.provider.search_decision_makers(BUSINESS)
        self.assertEqual(len(result['contacts']), 4)
        self.assertEqual(result['contacts'][0]['role_group'], 'general_manager')

    def test_same_person_on_two_pages_is_deduplicated(self, fetch):
        fetch.side_effect = [
            ('https://hotel.example/', '<a href="/team">Team</a>'
             '<p>John Smith — General Manager</p>'),
            ('https://hotel.example/team', '<p>John Smith — General Manager '
             '<a href="mailto:john@hotel.example">Email</a></p>'),
        ]
        result = self.provider.search_decision_makers(BUSINESS)
        self.assertEqual(len(result['contacts']), 1)
        self.assertEqual(result['contacts'][0]['business_email'], 'john@hotel.example')
        self.assertEqual(result['contacts'][0]['confidence'], 'HIGH')

    def test_optional_page_failure_preserves_home_result(self, fetch):
        fetch.side_effect = [
            ('https://hotel.example/', '<a href="/team">Team</a>'
             '<p>John Smith — General Manager</p>'),
            EnrichmentError('secondary failed'),
        ]
        result = self.provider.search_decision_makers(BUSINESS)
        self.assertEqual(result['status'], 'PARTIAL')
        self.assertEqual(result['contacts'][0]['name'], 'John Smith')

    def test_root_failure_is_clean_people_error(self, fetch):
        fetch.side_effect = EnrichmentError('private')
        with self.assertRaisesMessage(Exception, 'official business website'):
            self.provider.search_decision_makers(BUSINESS)


@override_settings(APOLLO_API_KEY='', ZOOMINFO_API_KEY='')
class OfficialWebsitePeopleIntegrationTests(APITestCase):
    settings_url = '/api/settings/providers/'

    def test_provider_is_keyless_and_selectable(self):
        response = self.client.put(
            self.settings_url, {'people_providers': ['official_website']}, format='json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['people_providers'], ['official_website'])

    @patch(
        'hotels.services.people_enrichment.providers.factory.'
        'OfficialWebsitePeopleEnrichmentProvider.search_decision_makers'
    )
    def test_existing_orchestrator_preserves_evidence(self, search):
        settings = ProviderSettings.load()
        settings.people_providers = ['official_website']
        settings.save()
        search.return_value = {
            'status': 'PARTIAL',
            'contacts': [{
                'name': 'John Smith', 'title': 'General Manager',
                'role_group': 'general_manager', 'organization_name': 'Example Hotel',
                'business_email': None, 'phone': None, 'linkedin_url': None,
                'source_url': 'https://hotel.example/team', 'confidence': 'HIGH',
            }],
        }
        result = search_decision_makers_multi_provider(
            BUSINESS, 'hotels_resorts', ['official_website'], settings
        )
        self.assertEqual(result['providers'], ['official_website'])
        self.assertEqual(result['contacts'][0]['source_url'], 'https://hotel.example/team')
        self.assertEqual(result['contacts'][0]['confidence'], 'HIGH')
        self.assertEqual(result['contacts'][0]['source'], 'Official Website')

    @patch('hotels.views.search_decision_makers_multi_provider')
    def test_existing_manager_api_accepts_official_website(self, search):
        settings = ProviderSettings.load()
        settings.people_providers = ['official_website']
        settings.save()
        search.return_value = {
            'business_name': 'Example Hotel', 'status': 'NOT_FOUND', 'contacts': [],
        }
        response = self.client.post('/api/hotels/enrich-managers/', {
            'name': 'Example Hotel', 'website': 'https://hotel.example/',
            'providers': ['official_website'],
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(search.call_args.kwargs['providers'], ['official_website'])
