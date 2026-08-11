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
    def test_maximum_three_page_limit(self, mock_get, mock_dns):
        home = '''
          <a href="/contact">Contact</a><a href="/reach-us">Reach us</a>
          <a href="/location">Location</a><a href="/about">About</a>
        '''
        mock_get.side_effect = [
            html_response(home), html_response('<p>Contact</p>'), html_response('<p>Reach</p>')
        ]
        enrich_hotel_from_website(self.hotel)
        self.assertEqual(mock_get.call_count, 3)

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
