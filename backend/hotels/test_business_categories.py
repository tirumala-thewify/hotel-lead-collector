from django.test import SimpleTestCase

from hotels.business_categories import (
    BUSINESS_CATEGORIES,
    get_business_categories,
    get_business_category,
)


class BusinessCategoryTests(SimpleTestCase):
    EXPECTED_CATEGORIES = {
        'hotels_resorts': ('Hotels & Resorts', [('tourism', 'hotel'), ('tourism', 'resort')]),
        'cafes': ('Cafés & Coffee Chains', [('amenity', 'cafe')]),
        'restaurants': ('Restaurants', [('amenity', 'restaurant')]),
        'shopping_malls': ('Shopping Malls', [('shop', 'mall')]),
        'hospitals': ('Hospitals', [('amenity', 'hospital')]),
        'coworking_spaces': ('Coworking Spaces', [('office', 'coworking')]),
        'salons_spas': ('Salons & Spas', [('shop', 'hairdresser'), ('shop', 'beauty')]),
        'gyms_fitness': ('Gyms & Fitness Centers', [('leisure', 'fitness_centre')]),
        'universities_colleges': (
            'Universities & Colleges',
            [('amenity', 'university'), ('amenity', 'college')],
        ),
        'schools': ('Schools', [('amenity', 'school')]),
        'airports': ('Airports', [('aeroway', 'aerodrome')]),
        'retail': ('Retail Stores / Retail Chains', [('shop', None)]),
        'event_venues': ('Event Venues', [('amenity', 'events_venue')]),
        'banks': ('Banks', [('amenity', 'bank')]),
        'petrol_stations': ('Petrol Stations', [('amenity', 'fuel')]),
        'pharmacies': ('Pharmacies', [('amenity', 'pharmacy')]),
        'hostels': ('Hostels', [('tourism', 'hostel')]),
    }

    def test_all_category_definitions(self):
        self.assertEqual(set(BUSINESS_CATEGORIES), set(self.EXPECTED_CATEGORIES))
        for category_id, (display_name, expected_tags) in self.EXPECTED_CATEGORIES.items():
            with self.subTest(category=category_id):
                category = get_business_category(category_id)
                self.assertEqual(category['id'], category_id)
                self.assertEqual(category['display_name'], display_name)
                self.assertEqual(
                    [(rule['key'], rule['value']) for rule in category['osm_tags']],
                    expected_tags,
                )

    def test_retail_uses_key_existence_rule(self):
        self.assertEqual(
            get_business_category('retail')['osm_tags'],
            [{'key': 'shop', 'value': None, 'match': 'exists'}],
        )

    def test_get_business_categories_returns_all_definitions(self):
        self.assertEqual(len(get_business_categories()), 17)

    def test_unknown_category_is_rejected(self):
        with self.assertRaisesMessage(ValueError, 'invalid_category'):
            get_business_category('invalid_category')
