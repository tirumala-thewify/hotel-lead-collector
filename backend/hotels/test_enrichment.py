from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

from hotels.services.enrichment.base import EnrichmentError
from hotels.services.enrichment.hotel_website import enrich_hotel_from_website
from hotels.services.enrichment.website_discovery import discover_official_website


PUBLIC_DNS = [(2, 1, 6, '', ('93.184.216.34', 443))]


def html_response(html, status=200, **headers):
    response = Mock()
    response.status_code = status
    response.headers = {'Content-Type': 'text/html; charset=utf-8', **headers}
    response.encoding = 'utf-8'
    response.is_redirect = status in {301, 302, 303, 307, 308}
    response.is_permanent_redirect = status in {301, 308}
    response.iter_content.return_value = [html.encode()]
    return response


@patch('hotels.services.enrichment.hotel_website.socket.getaddrinfo', return_value=PUBLIC_DNS)
class HotelWebsiteEnrichmentTests(SimpleTestCase):
    hotel = {'name': 'Example Hotel', 'website': 'https://hotel.example/'}

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_valid_website_enrichment(self, mock_get, mock_dns):
        home = '<a href="/contact">Contact</a>'
        contact = '<a href="tel:+91 1111111111">Call</a><a href="mailto:info@hotel.example">Email</a><address>12 Airport Road, Delhi</address>'
        mock_get.side_effect = [html_response(home), html_response(contact)]

        result = enrich_hotel_from_website(self.hotel)

        self.assertEqual(result['status'], 'FOUND')
        self.assertEqual(result['source_urls'], ['https://hotel.example/contact'])
        self.assertEqual(mock_get.call_count, 2)

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_same_domain_restriction(self, mock_get, mock_dns):
        mock_get.return_value = html_response(
            '<a href="https://vendor.example/contact">External contact</a>'
        )
        enrich_hotel_from_website(self.hotel)
        mock_get.assert_called_once()

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_maximum_five_page_limit(self, mock_get, mock_dns):
        home = '''
          <a href="/contact">Contact</a><a href="/about">About</a>
          <a href="/team">Team</a><a href="/leadership">Leadership</a>
          <a href="/management">Management</a><a href="/sales">Sales</a>
        '''
        mock_get.side_effect = [html_response(home)] + [html_response('<p>Page</p>')] * 4
        enrich_hotel_from_website(self.hotel)
        self.assertEqual(mock_get.call_count, 5)

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_secondary_404_preserves_homepage_data(self, mock_get, mock_dns):
        mock_get.side_effect = [
            html_response('<a href="/contact">Contact</a>'
                          '<a href="mailto:info@hotel.example">Email</a>'),
            html_response('', status=404),
        ]
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['email'], 'info@hotel.example')
        self.assertEqual(result['status'], 'PARTIAL')

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_secondary_timeout_preserves_homepage_data(self, mock_get, mock_dns):
        mock_get.side_effect = [
            html_response('<a href="/contact">Contact</a>'
                          '<a href="tel:+91 1234567890">Call</a>'),
            requests.Timeout,
        ]
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['phone'], '+91 1234567890')
        self.assertEqual(result['status'], 'PARTIAL')

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_secondary_403_preserves_homepage_data(self, mock_get, mock_dns):
        mock_get.side_effect = [
            html_response('<a href="/contact">Contact</a><address>Delhi</address>'),
            html_response('', status=403),
        ]
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['address'], 'Delhi')
        self.assertEqual(result['status'], 'PARTIAL')

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_one_secondary_failure_does_not_discard_another_success(self, mock_get, mock_dns):
        mock_get.side_effect = [
            html_response('<a href="/contact">Contact</a><a href="/about">About</a>'),
            html_response('', status=404),
            html_response('<a href="mailto:info@hotel.example">Email</a>'),
        ]
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['email'], 'info@hotel.example')
        self.assertEqual(result['sources']['email'], 'https://hotel.example/about')
        self.assertEqual(mock_get.call_count, 3)

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_root_failure_still_raises(self, mock_get, mock_dns):
        mock_get.return_value = html_response('', status=403)
        with self.assertRaisesMessage(EnrichmentError, 'HTTP 403'):
            enrich_hotel_from_website(self.hotel)

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_sales_classification_uses_positive_and_negative_context(self, mock_get, mock_dns):
        home = '''
          <a href="/sales">Sales</a>
          <a href="/corporate-sales">Corporate Sales</a>
          <a href="/group-sales">Group Sales</a>
          <a href="/information/legal/internet-sales-conditions.en.shtml">Terms</a>
          <a href="/legal/sales-conditions">Sales conditions</a>
        '''
        mock_get.side_effect = [html_response(home)] + [html_response('')] * 3
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['discovered_pages']['sales'], 'https://hotel.example/sales')
        self.assertNotIn('conditions', result['discovered_pages']['sales'])

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_corporate_and_group_sales_are_classified(self, mock_get, mock_dns):
        for path in ('corporate-sales', 'group-sales'):
            with self.subTest(path=path):
                mock_get.reset_mock()
                mock_get.side_effect = [
                    html_response(f'<a href="/{path}">{path}</a>'), html_response(''),
                ]
                result = enrich_hotel_from_website(self.hotel)
                self.assertEqual(
                    result['discovered_pages']['sales'], f'https://hotel.example/{path}'
                )

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_legal_sales_condition_pages_are_not_classified(self, mock_get, mock_dns):
        for path in (
            'information/legal/internet-sales-conditions.en.shtml',
            'legal/sales-conditions',
        ):
            with self.subTest(path=path):
                mock_get.reset_mock()
                mock_get.return_value = html_response(
                    f'<a href="/{path}">Sales terms</a>'
                )
                result = enrich_hotel_from_website(self.hotel)
                self.assertIsNone(result['discovered_pages']['sales'])
                mock_get.assert_called_once()

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_useful_page_discovery(self, mock_get, mock_dns):
        home = '''
          <a href="/contact-us">Contact</a><a href="/about-us">About</a>
          <a href="/our-team">Our Team</a><a href="/leadership">Leadership</a>
          <a href="/management">Management</a><a href="/sales">Sales</a>
          <a href="/news">News</a>
        '''
        mock_get.side_effect = [html_response(home)] + [html_response('')] * 4
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['discovered_pages'], {
            'contact': 'https://hotel.example/contact-us',
            'about': 'https://hotel.example/about-us',
            'team': 'https://hotel.example/our-team',
            'leadership': 'https://hotel.example/leadership',
            'management': 'https://hotel.example/management',
            'sales': 'https://hotel.example/sales',
            'press': 'https://hotel.example/news',
        })
        self.assertEqual(mock_get.call_count, 5)

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_social_profiles_found_and_source_tracked(self, mock_get, mock_dns):
        mock_get.return_value = html_response('''
          <footer>
            <a href="https://www.linkedin.com/company/example-hotel/">LinkedIn</a>
            <a href="https://facebook.com/examplehotel/">Facebook</a>
            <a href="https://www.instagram.com/examplehotel/">Instagram</a>
          </footer>
        ''')
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['social_profiles'], {
            'linkedin': 'https://www.linkedin.com/company/example-hotel',
            'facebook': 'https://facebook.com/examplehotel',
            'instagram': 'https://www.instagram.com/examplehotel',
        })
        self.assertEqual(result['social_profile_sources'], {
            'linkedin': 'https://hotel.example/',
            'facebook': 'https://hotel.example/',
            'instagram': 'https://hotel.example/',
        })
        mock_get.assert_called_once()

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_individual_social_profiles_are_found(self, mock_get, mock_dns):
        cases = (
            ('linkedin', 'https://linkedin.com/company/example', 'https://linkedin.com/company/example'),
            ('facebook', 'https://www.facebook.com/example', 'https://www.facebook.com/example'),
            ('instagram', 'https://instagram.com/example', 'https://instagram.com/example'),
        )
        for platform, url, expected in cases:
            with self.subTest(platform=platform):
                mock_get.reset_mock()
                mock_get.return_value = html_response(f'<a href="{url}">Profile</a>')
                result = enrich_hotel_from_website(self.hotel)
                self.assertEqual(result['social_profiles'][platform], expected)

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_duplicate_social_links_keep_first_url(self, mock_get, mock_dns):
        mock_get.return_value = html_response('''
          <a href="https://linkedin.com/company/first/">LinkedIn</a>
          <a href="https://www.linkedin.com/company/second/">LinkedIn again</a>
        ''')
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(
            result['social_profiles']['linkedin'], 'https://linkedin.com/company/first'
        )

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_invalid_fake_and_share_social_urls_are_ignored(self, mock_get, mock_dns):
        mock_get.return_value = html_response('''
          <a href="https://linkedin.com.example.com/company/fake">Fake</a>
          <a href="https://linkedin.com:bad/company/malformed">Malformed</a>
          <a href="https://www.linkedin.com/sharing/share-offsite/?url=x">Share</a>
          <a href="https://www.facebook.com/sharer/sharer.php?u=x">Share</a>
        ''')
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['social_profiles'], {
            'linkedin': None, 'facebook': None, 'instagram': None,
        })
        mock_get.assert_called_once()

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_social_url_on_contact_page_is_recorded_but_not_fetched(self, mock_get, mock_dns):
        mock_get.side_effect = [
            html_response('<a href="/contact">Contact</a>'),
            html_response('<a href="https://instagram.com/examplehotel">Instagram</a>'),
        ]
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(
            result['social_profiles']['instagram'], 'https://instagram.com/examplehotel'
        )
        self.assertEqual(
            result['social_profile_sources']['instagram'], 'https://hotel.example/contact'
        )
        self.assertEqual(mock_get.call_count, 2)
        requested_urls = [call.args[0] for call in mock_get.call_args_list]
        self.assertNotIn('https://instagram.com/examplehotel', requested_urls)

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_mailto_extraction(self, mock_get, mock_dns):
        mock_get.return_value = html_response('<a href="mailto:reservations@hotel.example">Book</a>')
        self.assertEqual(
            enrich_hotel_from_website(self.hotel)['email'],
            'reservations@hotel.example',
        )

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_tel_extraction(self, mock_get, mock_dns):
        mock_get.return_value = html_response('<a href="tel:+91-9876543210">Call</a>')
        self.assertEqual(enrich_hotel_from_website(self.hotel)['phone'], '+91-9876543210')

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_json_ld_extraction(self, mock_get, mock_dns):
        json_ld = '''<script type="application/ld+json">{
          "@type": "Hotel", "telephone": "+91 11 12345678",
          "email": "stay@hotel.example",
          "address": {"streetAddress": "12 Airport Road", "addressLocality": "Delhi"}
        }</script>'''
        mock_get.return_value = html_response(json_ld)
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['status'], 'FOUND')
        self.assertEqual(result['email'], 'stay@hotel.example')
        self.assertEqual(result['address'], '12 Airport Road, Delhi')

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_structured_phone_is_preferred_over_visible_phone(self, mock_get, mock_dns):
        mock_get.return_value = html_response(
            '<script type="application/ld+json">'
            '{"@type":"Hotel","telephone":"+91 11 1111 1111"}'
            '</script><a href="tel:+91 22 2222 2222">Call</a>'
        )
        self.assertEqual(
            enrich_hotel_from_website(self.hotel)['phone'], '+91 11 1111 1111'
        )

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_malformed_html_fails_safely(self, mock_get, mock_dns):
        mock_get.return_value = html_response('<html><script><div><<<<<')
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['status'], 'NOT_FOUND')

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_lodging_business_json_ld(self, mock_get, mock_dns):
        mock_get.return_value = html_response(
            '<script type="application/ld+json">'
            '{"@type":"LodgingBusiness","telephone":"+91 11 22222222"}'
            '</script>'
        )
        self.assertEqual(
            enrich_hotel_from_website(self.hotel)['phone'], '+91 11 22222222'
        )

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_organization_json_ld(self, mock_get, mock_dns):
        mock_get.return_value = html_response(
            '<script type="application/ld+json">'
            '{"@type":"Organization","email":"hotel@hotel.example"}'
            '</script>'
        )
        self.assertEqual(
            enrich_hotel_from_website(self.hotel)['email'], 'hotel@hotel.example'
        )

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_partial_result(self, mock_get, mock_dns):
        mock_get.return_value = html_response('<a href="tel:+91 1234567890">Call</a>')
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['status'], 'PARTIAL')

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_no_useful_contact_data(self, mock_get, mock_dns):
        mock_get.return_value = html_response('<h1>Welcome to our hotel</h1>')
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['status'], 'NOT_FOUND')
        self.assertEqual(result['source_urls'], [])

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_unrelated_email_is_rejected(self, mock_get, mock_dns):
        mock_get.return_value = html_response(
            '<a href="mailto:privacy@hotel.example">Privacy</a>'
            '<p>developer@vendor.example</p>'
        )
        self.assertIsNone(enrich_hotel_from_website(self.hotel)['email'])

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_visible_labelled_phone_extraction(self, mock_get, mock_dns):
        mock_get.return_value = html_response('<p>Reservations: +91 11 4444 5555</p>')
        self.assertEqual(
            enrich_hotel_from_website(self.hotel)['phone'], '+91 11 4444 5555'
        )

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_field_level_source_tracking(self, mock_get, mock_dns):
        mock_get.side_effect = [
            html_response('<a href="/contact-us">Contact us</a><address>Delhi</address>'),
            html_response('<a href="tel:+91 1234567890">Call</a>'
                          '<a href="mailto:info@hotel.example">Email</a>'),
        ]
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['sources']['website'], 'OpenStreetMap')
        self.assertEqual(result['sources']['address'], 'https://hotel.example/')
        self.assertEqual(result['sources']['phone'], 'https://hotel.example/contact-us')
        self.assertEqual(result['sources']['email'], 'https://hotel.example/contact-us')

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_incoming_business_source_is_preserved(self, mock_get, mock_dns):
        mock_get.return_value = html_response('<a href="tel:+91 1234567890">Call</a>')
        for source in ('Browser Search', 'OpenStreetMap'):
            with self.subTest(source=source):
                result = enrich_hotel_from_website({**self.hotel, 'source': source})
                self.assertEqual(result['sources']['website'], source)

    @patch('hotels.services.enrichment.hotel_website.requests.get', side_effect=requests.Timeout)
    def test_timeout(self, mock_get, mock_dns):
        with self.assertRaisesMessage(EnrichmentError, 'timed out'):
            enrich_hotel_from_website(self.hotel)

    @patch('hotels.services.enrichment.hotel_website.requests.get', side_effect=requests.ConnectionError)
    def test_connection_error(self, mock_get, mock_dns):
        with self.assertRaisesMessage(EnrichmentError, 'Could not connect'):
            enrich_hotel_from_website(self.hotel)

    def test_invalid_url(self, mock_dns):
        with self.assertRaisesMessage(EnrichmentError, 'invalid'):
            enrich_hotel_from_website({'name': 'Hotel', 'website': 'https://'})

    def test_localhost_is_blocked(self, mock_dns):
        with self.assertRaisesMessage(EnrichmentError, 'Local and private'):
            enrich_hotel_from_website({'name': 'Hotel', 'website': 'http://localhost/'})

    def test_private_ip_is_blocked(self, mock_dns):
        mock_dns.return_value = [(2, 1, 6, '', ('10.0.0.5', 80))]
        with self.assertRaisesMessage(EnrichmentError, 'Local and private'):
            enrich_hotel_from_website({'name': 'Hotel', 'website': 'http://10.0.0.5/'})

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_public_nat64_destination_is_allowed(self, mock_get, mock_dns):
        mock_dns.return_value = [(2, 1, 6, '', ('64:ff9b::4cdf:43bd', 443))]
        mock_get.return_value = html_response('<a href="tel:+91 1234567890">Call</a>')
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['phone'], '+91 1234567890')

    def test_unsupported_scheme_is_blocked(self, mock_dns):
        with self.assertRaisesMessage(EnrichmentError, 'Only HTTP and HTTPS'):
            enrich_hotel_from_website({'name': 'Hotel', 'website': 'file:///etc/passwd'})

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_redirect_to_private_destination_is_blocked(self, mock_get, mock_dns):
        mock_get.return_value = html_response('', status=302, Location='http://127.0.0.1/private')
        with self.assertRaisesMessage(EnrichmentError, 'Local and private'):
            enrich_hotel_from_website(self.hotel)
        mock_get.assert_called_once()


    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_all_business_contacts_are_deduplicated_with_sources(self, mock_get, mock_dns):
        mock_get.return_value = html_response('''
          <a href="mailto:info@hotel.example">Info</a>
          <a href="mailto:INFO@hotel.example">Info duplicate</a>
          <a href="mailto:sales@hotel.example">Sales</a>
          <a href="mailto:privacy@hotel.example">Privacy</a>
          <a href="mailto:test@example.com">Placeholder</a>
          <a href="tel:+91 12345 67890">Call</a>
          Phone: +91 12345 67890
        ''')
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(
            [(item['email'], item['type']) for item in result['business_emails']],
            [('info@hotel.example', 'general'), ('sales@hotel.example', 'sales')],
        )
        self.assertEqual(len(result['business_phones']), 1)
        self.assertEqual(result['business_phones'][0]['source_url'], 'https://hotel.example/')

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    def test_existing_scalar_fields_and_additive_schema_remain_compatible(self, mock_get, mock_dns):
        mock_get.return_value = html_response(
            '<a href="mailto:reservations@hotel.example">Book</a>'
            '<a href="tel:+1 212 555 0100">Call</a>'
        )
        result = enrich_hotel_from_website(self.hotel)
        self.assertEqual(result['email'], 'reservations@hotel.example')
        self.assertEqual(result['phone'], '+1 212 555 0100')
        self.assertIn('business_emails', result)
        self.assertIn('business_phones', result)
        self.assertIn('decision_makers', result)


class HotelEnrichmentAPITests(APITestCase):
    url = '/api/hotels/enrich/'

    @patch('hotels.views.enrich_hotel_from_website')
    def test_api_successful_response(self, mock_enrich):
        mock_enrich.return_value = {
            'hotel_name': 'Hotel Arch',
            'website': 'https://hotel.example/',
            'phone': '+91 1234567890',
            'email': 'info@hotel.example',
            'address': 'Delhi',
            'source_urls': ['https://hotel.example/contact'],
            'status': 'FOUND',
        }
        response = self.client.post(self.url, {
            'name': 'Hotel Arch', 'website': 'https://hotel.example/',
            'latitude': 28.5, 'longitude': 77.1,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'FOUND')
        mock_enrich.assert_called_once()

    @patch('hotels.views.enrich_hotel_from_website')
    def test_api_remains_backward_compatible_with_additive_fields(self, mock_enrich):
        mock_enrich.return_value = {
            'hotel_name': 'Hotel Arch', 'website': 'https://hotel.example/',
            'phone': None, 'email': None, 'address': None, 'brand': None,
            'source_urls': ['https://hotel.example/'],
            'sources': {'website': 'OpenStreetMap', 'phone': None, 'email': None,
                        'address': None, 'brand': None},
            'social_profiles': {'linkedin': 'https://linkedin.com/company/hotel-arch',
                                'facebook': None, 'instagram': None},
            'social_profile_sources': {'linkedin': 'https://hotel.example/',
                                       'facebook': None, 'instagram': None},
            'discovered_pages': {'contact': None, 'about': None, 'team': None,
                                 'leadership': None, 'management': None,
                                 'sales': None, 'press': None},
            'status': 'PARTIAL',
        }
        response = self.client.post(self.url, {
            'name': 'Hotel Arch', 'website': 'https://hotel.example/',
        }, format='json')
        data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertIn('hotel_name', data)
        self.assertIn('phone', data)
        self.assertEqual(
            data['social_profiles']['linkedin'],
            'https://linkedin.com/company/hotel-arch',
        )

    @patch('hotels.views.enrich_hotel_from_website')
    def test_api_missing_website_response(self, mock_enrich):
        mock_enrich.return_value = {
            'hotel_name': 'Hotel Arch', 'website': None, 'phone': None,
            'email': None, 'address': None, 'brand': None, 'source_urls': [],
            'sources': {'website': None, 'phone': None, 'email': None, 'address': None, 'brand': None},
            'status': 'NOT_FOUND',
            'message': 'No official website is available for enrichment.',
        }
        response = self.client.post(self.url, {'name': 'Hotel Arch'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'NOT_FOUND')
        self.assertEqual(
            response.json()['message'],
            'No official website is available for enrichment.',
        )
        mock_enrich.assert_called_once()

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    @patch('hotels.services.enrichment.hotel_website.socket.getaddrinfo', return_value=PUBLIC_DNS)
    def test_http_error_statuses_are_safe(self, mock_dns, mock_get):
        for status in (403, 429, 500):
            mock_get.return_value = html_response('', status=status)
            with self.subTest(status=status), self.assertRaisesMessage(EnrichmentError, f'HTTP {status}'):
                enrich_hotel_from_website({'name': 'Example', 'website': 'https://hotel.example/'})

    @patch('hotels.services.enrichment.hotel_website.requests.get')
    @patch('hotels.services.enrichment.hotel_website.socket.getaddrinfo', return_value=PUBLIC_DNS)
    def test_non_html_response_is_rejected(self, mock_dns, mock_get):
        mock_get.return_value = html_response('not html', **{'Content-Type': 'application/json'})
        with self.assertRaisesMessage(EnrichmentError, 'HTML'):
            enrich_hotel_from_website({'name': 'Example', 'website': 'https://hotel.example/'})


class WebsiteDiscoveryTests(SimpleTestCase):
    @patch('hotels.services.enrichment.website_discovery.requests.get')
    def test_wikidata_official_website_is_high_confidence(self, mock_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'entities': {'Q123': {'claims': {'P856': [{
            'mainsnak': {'datavalue': {'value': 'https://official.example/hotel'}}
        }]}}}}
        mock_get.return_value = response
        result = discover_official_website('Hotel', wikidata='Q123')
        self.assertEqual(result['website'], 'https://official.example/hotel')
        self.assertEqual(result['confidence'], 'HIGH')

    def test_existing_brand_hint_is_medium_confidence(self):
        result = discover_official_website(
            'Hotel', brand_website='https://brand.example/hotel'
        )
        self.assertEqual(result['confidence'], 'MEDIUM')
