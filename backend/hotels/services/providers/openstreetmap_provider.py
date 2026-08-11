from ..openstreetmap import search_nearby_hotels
from .base import HotelProvider


class OpenStreetMapProvider(HotelProvider):
    def search_nearby_hotels(self, latitude, longitude, radius):
        return search_nearby_hotels(latitude, longitude, radius)
