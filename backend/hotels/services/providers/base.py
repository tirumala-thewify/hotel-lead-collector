from abc import ABC, abstractmethod


class HotelProvider(ABC):
    @abstractmethod
    def search_nearby_hotels(self, latitude, longitude, radius):
        raise NotImplementedError


class HotelProviderConfigurationError(Exception):
    """Raised when a selected provider lacks required configuration."""
