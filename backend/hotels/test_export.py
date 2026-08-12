from io import BytesIO
from unittest.mock import patch

from django.test import SimpleTestCase
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from hotels.export_api import MAX_EXPORT_ROWS
from hotels.services.export.excel import build_hotel_workbook, export_columns


CONTEXT = {
    'location': 'Delhi Airport',
    'latitude': 28.5562,
    'longitude': 77.1,
    'radius': 5000,
    'provider': 'OpenStreetMap',
}

HOTEL = {
    'name': 'Roseate House',
    'distance_km': 2.1,
    'address': 'Aerocity, New Delhi',
    'phone': '+911171558800',
    'email': 'info@roseatehotels.com',
    'website': 'https://www.roseatehotels.com/',
    'brand': 'Roseate Hotels',
    'stars': '5',
    'latitude': 28.55,
    'longitude': 77.12,
    'source': 'OpenStreetMap',
    'enrichment_status': 'FOUND',
    'enrichment_sources': {
        'address': 'OpenStreetMap',
        'phone': 'https://www.roseatehotels.com/contact',
        'email': 'https://www.roseatehotels.com/contact',
        'website': 'OpenStreetMap',
        'brand': 'OpenStreetMap',
    },
    'manager_contacts': [{
        'name': 'Manager Name',
        'title': 'General Manager',
        'department': 'General Management',
        'email': 'manager@roseatehotels.com',
        'phone': '+911112345678',
        'linkedin_url': 'https://linkedin.com/in/manager',
    }],
}


class ExcelWorkbookTests(SimpleTestCase):
    def workbook(self, hotels=None):
        data, _ = build_hotel_workbook(hotels or [HOTEL], CONTEXT)
        return load_workbook(BytesIO(data))

    def test_workbook_contains_search_summary(self):
        self.assertIn('Search Summary', self.workbook().sheetnames)

    def test_workbook_contains_hotels(self):
        self.assertIn('Hotels', self.workbook().sheetnames)

    def test_workbook_contains_structured_enrichment_sheets(self):
        hotel = {
            **HOTEL,
            'business_emails': [{'email': 'sales@hotel.example', 'type': 'sales',
                                 'source_url': 'https://hotel.example/contact'}],
            'business_phones': [{'phone': '+1 212 555 0100', 'type': 'general',
                                 'source_url': 'https://hotel.example/contact'}],
            'decision_makers': [{'name': 'Jane Doe', 'title': 'IT Director',
                                 'department': 'Information Technology',
                                 'role_group': 'it_leadership',
                                 'source_url': 'https://hotel.example/team'}],
            'social_profiles': {'linkedin': 'https://linkedin.com/company/hotel'},
            'social_profile_sources': {'linkedin': 'https://hotel.example/'},
        }
        workbook = self.workbook([hotel])
        self.assertIn('Business Contacts', workbook.sheetnames)
        self.assertIn('Decision Makers', workbook.sheetnames)
        self.assertIn('Social Profiles', workbook.sheetnames)
        self.assertEqual(workbook['Business Contacts'].max_row, 3)
        self.assertEqual(workbook['Decision Makers'].cell(2, 2).value, 'Jane Doe')
        self.assertEqual(workbook['Social Profiles'].cell(2, 2).value, 'Linkedin')

    def test_headers_are_correct(self):
        sheet = self.workbook()['Hotels']
        self.assertEqual(
            [cell.value for cell in sheet[1]],
            [label for label, _ in export_columns()],
        )

    def test_hotel_row_values(self):
        row = self.workbook()['Hotels'][2]
        self.assertEqual(row[1].value, 'Roseate House')
        self.assertEqual(row[2].value, 2.1)

    def test_phone_plus_prefix_is_preserved_safely(self):
        phone = self.workbook()['Hotels'].cell(2, 5)
        self.assertEqual(phone.value, "'+911171558800")
        self.assertEqual(phone.number_format, '@')

    def test_unicode_hotel_name_is_preserved(self):
        hotel = {**HOTEL, 'name': 'होटल स्वागत'}
        self.assertEqual(self.workbook([hotel])['Hotels'].cell(2, 2).value, 'होटल स्वागत')

    def test_website_hyperlink(self):
        cell = self.workbook()['Hotels'].cell(2, 7)
        self.assertEqual(cell.hyperlink.target, HOTEL['website'])

    def test_manager_columns(self):
        sheet = self.workbook()['Hotels']
        self.assertEqual(sheet.cell(2, 14).value, 'Manager Name')
        self.assertEqual(sheet.cell(2, 18).hyperlink.target, 'https://linkedin.com/in/manager')

    def test_field_source_columns(self):
        sheet = self.workbook()['Hotels']
        headers = [cell.value for cell in sheet[1]]
        phone_source_column = headers.index('Phone Source') + 1
        self.assertEqual(
            sheet.cell(2, phone_source_column).value,
            'https://www.roseatehotels.com/contact',
        )

    def test_missing_values_are_blank(self):
        hotel = {'name': 'Minimal Hotel'}
        sheet = self.workbook([hotel])['Hotels']
        self.assertIsNone(sheet.cell(2, 4).value)
        self.assertIsNone(sheet.cell(2, 14).value)

    def test_formula_injection_is_escaped(self):
        hotel = {**HOTEL, 'name': '=HYPERLINK("https://bad.example")'}
        value = self.workbook([hotel])['Hotels'].cell(2, 2).value
        self.assertTrue(value.startswith("'="))


class ExcelExportAPITests(APITestCase):
    url = '/api/hotels/export/excel/'

    def payload(self, hotels=None):
        return {'hotels': [HOTEL] if hotels is None else hotels, 'context': CONTEXT}

    def test_excel_export_success(self):
        response = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('hotel-leads-delhi-airport-', response['Content-Disposition'])

    def test_invalid_hotels_payload(self):
        response = self.client.post(
            self.url, {'hotels': 'not-a-list', 'context': CONTEXT}, format='json'
        )
        self.assertEqual(response.status_code, 400)

    def test_empty_list_handling(self):
        response = self.client.post(self.url, self.payload([]), format='json')
        self.assertEqual(response.status_code, 400)

    def test_row_limit_validation(self):
        hotels = [{'name': f'Hotel {index}'} for index in range(MAX_EXPORT_ROWS + 1)]
        response = self.client.post(self.url, self.payload(hotels), format='json')
        self.assertEqual(response.status_code, 400)

    @patch('requests.get')
    @patch('requests.post')
    def test_export_does_not_call_external_apis(self, mock_post, mock_get):
        response = self.client.post(self.url, self.payload(), format='json')
        self.assertEqual(response.status_code, 200)
        mock_get.assert_not_called()
        mock_post.assert_not_called()
