from django.test import SimpleTestCase

from hotels.services.people_enrichment.role_profiles import (
    ROLE_PROFILES,
    get_role_profile,
)


class DecisionMakerRoleProfileTests(SimpleTestCase):
    def test_all_business_categories_have_profiles(self):
        self.assertEqual(set(ROLE_PROFILES), {
            'hotels_resorts', 'cafes', 'restaurants', 'shopping_malls',
            'hospitals', 'coworking_spaces', 'salons_spas', 'gyms_fitness',
            'universities_colleges', 'schools', 'airports', 'retail',
            'event_venues', 'banks', 'petrol_stations', 'pharmacies', 'hostels',
        })

    def test_required_representative_titles(self):
        expectations = {
            'hotels_resorts': ('General Manager', 'Marketing Manager', 'IT Manager'),
            'schools': ('Principal', 'Director', 'IT Manager'),
            'hospitals': ('Hospital Administrator', 'Marketing Manager', 'IT Manager'),
            'restaurants': ('Owner', 'General Manager', 'Operations Manager'),
            'universities_colleges': ('Director', 'Registrar', 'IT Director'),
            'retail': ('Store Manager', 'Marketing Manager', 'IT Manager'),
        }
        for category, titles in expectations.items():
            with self.subTest(category=category):
                configured = {
                    title
                    for group_titles in get_role_profile(category).values()
                    for title in group_titles
                }
                self.assertTrue(set(titles).issubset(configured))

    def test_unknown_category_is_rejected(self):
        with self.assertRaisesMessage(ValueError, 'invalid_category'):
            get_role_profile('invalid_category')
