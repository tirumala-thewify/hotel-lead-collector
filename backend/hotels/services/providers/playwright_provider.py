from django.conf import settings

from hotels.business_categories import get_business_category
from hotels.services.openstreetmap import calculate_distance_km

from ..scraping import MapsScraper, ScraperError
from .base import HotelProvider


class PlaywrightProviderError(Exception):
    """Raised when browser-backed business discovery fails safely."""


MAPS_CATEGORY_QUERIES = {
    'hotels_resorts': 'hotels',
    'cafes': 'cafes',
    'restaurants': 'restaurants',
    'shopping_malls': 'shopping malls',
    'hospitals': 'hospitals',
    'coworking_spaces': 'coworking spaces',
    'salons_spas': 'salons and spas',
    'gyms_fitness': 'gyms and fitness centers',
    'universities_colleges': 'universities and colleges',
    'schools': 'schools',
    'airports': 'airports',
    'retail': 'retail stores',
    'event_venues': 'event venues',
    'banks': 'banks',
    'petrol_stations': 'petrol stations',
    'pharmacies': 'pharmacies',
    'hostels': 'hostels',
}


class PlaywrightProvider(HotelProvider):
    def __init__(self, scraper=None):
        self.scraper = scraper or MapsScraper()

    def search_nearby_hotels(self, latitude, longitude, radius):
        return self.search_nearby_businesses(latitude, longitude, radius, 'hotels_resorts')

    def search_nearby_businesses(self, latitude, longitude, radius, category='hotels_resorts'):
        get_business_category(category)
        query = MAPS_CATEGORY_QUERIES[category]
        try:
            results = self.scraper.search(query=query, latitude=latitude, longitude=longitude, category=category, max_results=settings.PLAYWRIGHT_MAX_RESULTS)
        except (ScraperError, ValueError, TypeError) as exc:
            raise PlaywrightProviderError('Browser business search failed.') from exc
        for result in results:
            result['distance_km'] = calculate_distance_km(latitude, longitude, result.get('latitude'), result.get('longitude'))
        return [result for result in results if result.get('distance_km') is None or result['distance_km'] <= radius / 1000]
