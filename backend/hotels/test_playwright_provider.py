from contextlib import contextmanager
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings

from hotels.models import ProviderSettings
from hotels.services.providers.factory import get_business_provider
from hotels.services.providers.orchestrator import search_businesses_multi_provider
from hotels.services.providers.playwright_provider import (
    CATEGORY_SEARCH_TERMS, PlaywrightProvider, PlaywrightProviderError,
)
from hotels.services.scraping.browser import BrowserStartupError, browser_page
from hotels.services.scraping.maps_scraper import (
    DETAIL_SELECTORS, MapsScraper, ScraperError,
)
from hotels.services.scraping.parsers import (
    deduplicate_listings, listing_identity, normalize_listing, place_identifier,
)


@override_settings(
    PLAYWRIGHT_MAX_RESULTS=20, PLAYWRIGHT_MAX_RESULTS_PER_QUERY=20,
    PLAYWRIGHT_MAX_TOTAL_RESULTS=40,
)
class PlaywrightProviderTests(SimpleTestCase):
    def test_success_forwards_category_and_coordinates(self):
        scraper = Mock()
        scraper.search_many.return_value = [{
            'name': 'River Hotel', 'latitude': 16.5062, 'longitude': 80.648,
        }]
        results = PlaywrightProvider(scraper).search_nearby_businesses(
            16.5062, 80.648, 5000, 'hotels_resorts'
        )
        self.assertEqual(results[0]['name'], 'River Hotel')
        call = scraper.search_many.call_args.kwargs
        self.assertEqual(call['queries'], ('hotels', 'resorts'))
        self.assertEqual((call['latitude'], call['longitude']), (16.5062, 80.648))

    def test_combined_categories_use_concise_terms(self):
        expected = {
            'hotels_resorts': ('hotels', 'resorts'),
            'cafes': ('cafes', 'coffee shops'),
            'salons_spas': ('salons', 'spas'),
            'gyms_fitness': ('gyms', 'fitness centers'),
        }
        for category, terms in expected.items():
            with self.subTest(category=category):
                scraper = Mock()
                scraper.search_many.return_value = []
                PlaywrightProvider(scraper).search_nearby_businesses(1, 2, 1000, category)
                self.assertEqual(scraper.search_many.call_args.kwargs['queries'], terms)

    def test_single_term_category_runs_once(self):
        scraper = Mock()
        scraper.search_many.return_value = []
        PlaywrightProvider(scraper).search_nearby_businesses(1, 2, 1000, 'restaurants')
        self.assertEqual(scraper.search_many.call_args.kwargs['queries'], ('restaurants',))

    def test_mapping_covers_existing_categories(self):
        from hotels.business_categories import BUSINESS_CATEGORIES
        self.assertEqual(set(CATEGORY_SEARCH_TERMS), set(BUSINESS_CATEGORIES))

    def test_unknown_category_remains_rejected(self):
        with self.assertRaises(ValueError):
            PlaywrightProvider(Mock()).search_nearby_businesses(1, 2, 1000, 'unknown')

    def test_empty_results(self):
        scraper = Mock()
        scraper.search_many.return_value = []
        self.assertEqual(PlaywrightProvider(scraper).search_nearby_hotels(1, 2, 1000), [])

    def test_scraper_failure_becomes_controlled_provider_error(self):
        scraper = Mock()
        scraper.search_many.side_effect = ScraperError('private browser detail')
        with self.assertRaisesMessage(PlaywrightProviderError, 'Browser business search failed'):
            PlaywrightProvider(scraper).search_nearby_hotels(1, 2, 1000)

    def test_factory_returns_provider_without_api_key(self):
        self.assertIsInstance(get_business_provider('playwright', Mock()), PlaywrightProvider)


class ParserTests(SimpleTestCase):
    def test_all_detail_fields_use_canonical_schema(self):
        result = normalize_listing({
            'name': 'Complete Hotel',
            'address': 'Address: MG Road',
            'phone': 'Phone: 0866 123 4567',
            'website': 'https://hotel.test',
            'rating': '4.4 stars',
            'review_count': '1,234 reviews',
            'opening_hours': 'Hours: Open 24 hours',
            'maps_url': 'https://maps.test/place/data=!3d16.5!4d80.6!19sChIJcomplete',
        }, 'hotels_resorts')
        self.assertEqual(result['address'], 'MG Road')
        self.assertEqual(result['phone'], '0866 123 4567')
        self.assertEqual(result['website'], 'https://hotel.test')
        self.assertEqual((result['rating'], result['review_count']), (4.4, 1234))
        self.assertEqual(result['opening_hours'], 'Open 24 hours')
        self.assertEqual((result['id'], result['place_id']), ('ChIJcomplete', 'ChIJcomplete'))

    def test_google_place_identifier_is_parsed_from_live_maps_url(self):
        self.assertEqual(place_identifier(
            'https://www.google.com/maps/place/Hotel/data=!8m2!3d16.5!4d80.6!19sChIJabc123?hl=en'
        ), 'ChIJabc123')

    def test_missing_fields_are_null_and_coordinates_are_parsed(self):
        result = normalize_listing({
            'name': 'Cafe One',
            'maps_url': 'https://www.google.com/maps/place/x/@16.5,80.6,17z',
        }, 'cafes')
        self.assertEqual((result['latitude'], result['longitude']), (16.5, 80.6))
        for field in ('phone', 'website', 'rating', 'review_count', 'opening_hours'):
            self.assertIsNone(result[field])

    def test_coordinates_are_parsed_from_maps_data_url(self):
        result = normalize_listing({
            'name': 'The Umrao',
            'maps_url': (
                'https://www.google.com/maps/place/The+Umrao/'
                'data=!4m10!8m2!3d28.5252863!4d77.1001887!16s%2Fg%2F11b5wjn4p9'
            ),
        }, 'hotels_resorts')
        self.assertEqual((result['latitude'], result['longitude']), (28.5252863, 77.1001887))

    def test_unavailable_coordinates_remain_null(self):
        result = normalize_listing({
            'name': 'List-only Hotel',
            'maps_url': 'https://www.google.com/maps/place/List-only+Hotel',
        }, 'hotels_resorts')
        self.assertEqual((result['latitude'], result['longitude']), (None, None))

    def test_partial_raw_coordinates_remain_partial_without_url_coordinates(self):
        result = normalize_listing({
            'name': 'Partial Hotel', 'latitude': 28.5,
            'maps_url': 'https://www.google.com/maps/place/Partial+Hotel',
        }, 'hotels_resorts')
        self.assertEqual((result['latitude'], result['longitude']), (28.5, None))

    def test_rating_and_review_count(self):
        result = normalize_listing({
            'name': 'Cafe One', 'rating': '4.6 stars', 'review_count': '4.6 (1,234)',
        }, 'cafes')
        self.assertEqual((result['rating'], result['review_count']), (4.6, 1234))

    def test_duplicate_maps_urls_and_name_address(self):
        first = {'name': 'One', 'address': 'Road', 'maps_url': 'https://maps.test/?query_place_id=abc'}
        same_url = {**first, 'name': 'Changed'}
        no_url = {'name': 'Two', 'address': 'Lane', 'maps_url': None}
        self.assertEqual(len(deduplicate_listings([first, same_url, no_url, dict(no_url)])), 2)

    def test_identity_prefers_place_id_then_name_address_and_coordinates(self):
        self.assertEqual(listing_identity({'place_id': 'abc', 'maps_url': 'other'}), ('place_id', 'abc'))
        self.assertEqual(
            listing_identity({'name': ' Hotel One ', 'address': ' Main Road '}),
            ('name_address', 'hotel one', 'main road'),
        )
        self.assertEqual(
            listing_identity({'name': 'Hotel One', 'latitude': 1, 'longitude': 2}),
            ('name_coordinates', 'hotel one', 1, 2),
        )


class MapsScraperFailureTests(SimpleTestCase):
    def test_multi_query_deduplicates_before_detail_extraction_and_caps_results(self):
        scraper = MapsScraper()
        scraper._search_cards = Mock(side_effect=[
            [
                {'name': 'Same Hotel', 'maps_url': 'https://maps.test/?query_place_id=same'},
                {'name': 'Hotel Two', 'address': 'Road Two'},
            ],
            [
                {'name': 'Same Changed', 'maps_url': 'https://maps.test/?query_place_id=same'},
                {'name': 'Hotel Two', 'address': 'Road Two'},
                {'name': 'Hotel Three', 'address': 'Road Three'},
            ],
        ])
        scraper._extract_raw_results = Mock(side_effect=lambda _page, raw, _category: raw)
        @contextmanager
        def page(**kwargs):
            yield Mock()
        scraper.page_factory = page
        result = scraper.search_many(
            queries=('hotels', 'resorts'), latitude=1, longitude=2,
            category='hotels_resorts', max_results_per_query=2, max_total_results=2,
        )
        self.assertEqual(len(result), 2)
        raw = scraper._extract_raw_results.call_args.args[1]
        self.assertEqual(len(raw), 2)
        self.assertEqual(scraper._search_cards.call_args_list[0].args[-1], 2)

    def test_multi_query_partial_failure_preserves_success(self):
        scraper = MapsScraper()
        scraper._search_cards = Mock(side_effect=[
            [{'name': 'Hotel One', 'address': 'Road'}], RuntimeError('timeout'),
        ])
        scraper._extract_raw_results = Mock(side_effect=lambda _page, raw, _category: raw)
        @contextmanager
        def page(**kwargs):
            yield Mock()
        scraper.page_factory = page
        result = scraper.search_many(
            queries=('hotels', 'resorts'), latitude=1, longitude=2,
            category='hotels_resorts', max_results_per_query=20, max_total_results=40,
        )
        self.assertEqual([item['name'] for item in result], ['Hotel One'])
        self.assertEqual(scraper.last_query_results['hotels']['status'], 'success')
        self.assertEqual(scraper.last_query_results['hotels']['unique_added'], 1)
        self.assertEqual(scraper.last_query_results['resorts']['status'], 'error')

    def test_duplicate_card_opens_details_once(self):
        scraper = MapsScraper()
        raw = [
            {'name': 'One', 'maps_url': 'https://maps.test/?query_place_id=abc'},
            {'name': 'Again', 'maps_url': 'https://maps.test/?query_place_id=abc'},
        ]
        unique = scraper._deduplicate_raw_listings(raw)
        scraper.open_listing = Mock()
        scraper.extract_listing_details = Mock(return_value={})
        scraper._extract_raw_results(Mock(), unique, 'hotels_resorts')
        scraper.open_listing.assert_called_once()

    def test_detail_selectors_extract_all_available_fields(self):
        scraper, page = MapsScraper(), Mock()
        values = {
            DETAIL_SELECTORS['address'][0]: 'Address: MG Road',
            DETAIL_SELECTORS['phone'][0]: 'Phone: 0866 123 4567',
            DETAIL_SELECTORS['website'][0]: 'https://hotel.test',
            DETAIL_SELECTORS['opening_hours'][0]: 'Hours: Open 24 hours',
            DETAIL_SELECTORS['review_count'][0]: '1,234 reviews',
        }

        def locator(selector):
            result = Mock()
            value = values.get(selector)
            result.count.return_value = int(value is not None)
            result.first.get_attribute.return_value = value
            return result

        page.locator.side_effect = locator
        self.assertEqual(scraper.extract_listing_details(page), {
            'address': 'Address: MG Road', 'phone': 'Phone: 0866 123 4567',
            'website': 'https://hotel.test', 'opening_hours': 'Hours: Open 24 hours',
            'review_count': '1,234 reviews',
        })

    def test_missing_detail_selectors_return_null(self):
        page = Mock()
        page.locator.return_value.count.return_value = 0
        self.assertEqual(MapsScraper().extract_listing_details(page), {
            'address': None, 'phone': None, 'website': None,
            'opening_hours': None, 'review_count': None,
        })

    def test_browser_launch_failure(self):
        @contextmanager
        def failed_page(**kwargs):
            raise BrowserStartupError('Chromium missing')
            yield
        with self.assertRaisesMessage(ScraperError, 'Chromium missing'):
            MapsScraper(failed_page).search(
                query='hotels', latitude=1, longitude=2, category='hotels_resorts', max_results=5
            )

    def test_navigation_timeout(self):
        class TimeoutError(Exception):
            pass
        page = Mock()
        page.goto.side_effect = TimeoutError
        @contextmanager
        def timed_out_page(**kwargs):
            yield page
        with self.assertRaisesMessage(ScraperError, 'timed out'):
            MapsScraper(timed_out_page).search(
                query='hotels', latitude=1, longitude=2, category='hotels_resorts', max_results=5
            )

    def test_zero_results_page_returns_empty_list(self):
        class TimeoutError(Exception):
            pass
        page, feed, no_results = Mock(), Mock(), Mock()
        feed.wait_for.side_effect = TimeoutError
        no_results.count.return_value = 1
        page.locator.return_value = feed
        page.get_by_text.return_value = no_results
        @contextmanager
        def empty_page(**kwargs):
            yield page
        self.assertEqual(MapsScraper(empty_page).search(
            query='hotels', latitude=1, longitude=2, category='hotels_resorts', max_results=5
        ), [])

    def test_parsing_failure_on_one_listing_keeps_other_results(self):
        scraper = MapsScraper()
        bad, good, cards = Mock(), Mock(), Mock()
        cards.count.return_value = 2
        cards.nth.side_effect = [bad, good]
        bad.locator.side_effect = RuntimeError('DOM changed')
        link = Mock()
        link.first = link
        link.get_attribute.side_effect = ['Good Hotel', 'https://maps.test/good']
        good.locator.return_value = link
        scraper._attribute = Mock(return_value=None)
        scraper.extract_listing_details = Mock(return_value={})
        results = scraper._extract_results(Mock(locator=Mock(return_value=cards)), 'hotels_resorts', 5)
        self.assertEqual([item['name'] for item in results], ['Good Hotel'])

    def test_one_detail_navigation_failure_keeps_all_card_results(self):
        scraper, cards, first, second = MapsScraper(), Mock(), Mock(), Mock()
        first_link, second_link = Mock(), Mock()
        first_link.first, second_link.first = first_link, second_link
        first_link.get_attribute.side_effect = ['First Hotel', 'https://maps.test/first']
        second_link.get_attribute.side_effect = ['Second Hotel', 'https://maps.test/second']
        first.locator.return_value, second.locator.return_value = first_link, second_link
        first.inner_text.return_value = second.inner_text.return_value = ''
        cards.count.return_value = 2
        cards.nth.side_effect = [first, second]
        page = Mock()
        page.locator.return_value = cards
        scraper._attribute = Mock(return_value=None)
        scraper.open_listing = Mock(side_effect=[RuntimeError('detail failed'), None])
        scraper.extract_listing_details = Mock(return_value={
            'address': 'Address: Second Road', 'phone': None, 'website': None,
            'opening_hours': None, 'review_count': None,
        })
        results = scraper._extract_results(page, 'hotels_resorts', 5)
        self.assertEqual([result['name'] for result in results], ['First Hotel', 'Second Hotel'])
        self.assertIsNone(results[0]['address'])
        self.assertEqual(results[1]['address'], 'Second Road')

    @override_settings(
        PLAYWRIGHT_MAX_RESULTS_PER_QUERY=20, PLAYWRIGHT_MAX_TOTAL_RESULTS=40,
    )
    def test_provider_excludes_business_outside_radius(self):
        scraper = Mock()
        scraper.search_many.return_value = [
            {'name': 'Near', 'latitude': 1, 'longitude': 2},
            {'name': 'Far', 'latitude': 20, 'longitude': 20},
        ]
        results = PlaywrightProvider(scraper).search_nearby_businesses(
            1, 2, 5000, 'hotels_resorts'
        )
        self.assertEqual([item['name'] for item in results], ['Near'])


class BrowserCleanupTests(SimpleTestCase):
    def test_resources_close_after_page_exception(self):
        manager, browser, context, page = Mock(), Mock(), Mock(), Mock()
        manager.chromium.launch.return_value = browser
        browser.new_context.return_value = context
        context.new_page.return_value = page
        fake_module = Mock()
        fake_module.sync_playwright.return_value.start.return_value = manager
        with patch.dict('sys.modules', {'playwright': Mock(), 'playwright.sync_api': fake_module}):
            with self.assertRaises(RuntimeError):
                with browser_page():
                    raise RuntimeError('failure')
        page.close.assert_called_once()
        context.close.assert_called_once()
        browser.close.assert_called_once()
        manager.stop.assert_called_once()


class PlaywrightOrchestrationTests(SimpleTestCase):
    def test_partial_failure_preserves_existing_provider_results(self):
        settings_record = Mock()
        settings_record.business_providers = ['openstreetmap', 'playwright']
        settings_record.hotel_provider = 'openstreetmap'
        osm, browser = Mock(), Mock()
        osm.search_nearby_businesses.return_value = [{
            'name': 'OSM Hotel', 'latitude': 1, 'longitude': 2,
        }]
        browser.search_nearby_businesses.side_effect = PlaywrightProviderError('failed')
        with patch('hotels.services.providers.orchestrator.get_business_provider', side_effect=[osm, browser]):
            result = search_businesses_multi_provider(
                1, 2, 1000, 'hotels_resorts', ['openstreetmap', 'playwright'], settings_record
            )
        self.assertEqual(result['provider_results']['playwright']['status'], 'error')
        self.assertEqual(result['hotels'][0]['name'], 'OSM Hotel')


class PlaywrightNearbyAPITests(TestCase):
    def test_invalid_provider_remains_rejected(self):
        response = self.client.get('/api/hotels/nearby/', {
            'lat': 1, 'lng': 2, 'radius': 1000, 'providers': 'not-a-provider',
        })
        self.assertEqual(response.status_code, 400)

    @patch('hotels.views.search_businesses_multi_provider')
    def test_existing_endpoint_accepts_playwright(self, search):
        search.return_value = {
            'hotels': [], 'providers': ['playwright'],
            'provider_results': {'playwright': {'status': 'success', 'count': 0}},
            'raw_result_count': 0, 'deduplicated_count': 0,
        }
        settings_record = ProviderSettings.load()
        settings_record.business_providers = ['playwright']
        settings_record.save()
        response = self.client.get('/api/hotels/nearby/', {
            'lat': 1, 'lng': 2, 'radius': 1000, 'providers': 'playwright',
        })
        self.assertEqual(response.status_code, 200)

    @patch('hotels.views.search_businesses_multi_provider')
    def test_api_preserves_playwright_detail_fields(self, search):
        hotel = {
            'name': 'Complete Hotel', 'address': 'MG Road',
            'phone': '0866 123 4567', 'website': 'https://hotel.test',
            'rating': 4.4, 'review_count': 1234, 'opening_hours': 'Open 24 hours',
            'latitude': 16.5, 'longitude': 80.6, 'source': 'Browser Search',
        }
        search.return_value = {
            'hotels': [hotel], 'providers': ['playwright'],
            'provider_results': {'playwright': {'status': 'success', 'count': 1}},
            'raw_result_count': 1, 'deduplicated_count': 1,
        }
        settings_record = ProviderSettings.load()
        settings_record.business_providers = ['playwright']
        settings_record.save()
        response = self.client.get('/api/hotels/nearby/', {
            'lat': 16.5, 'lng': 80.6, 'radius': 5000, 'providers': 'playwright',
        })
        self.assertEqual(response.status_code, 200)
        for field, value in hotel.items():
            self.assertEqual(response.json()['hotels'][0][field], value)
