from abc import ABC, abstractmethod


class PeopleEnrichmentProvider(ABC):
    @abstractmethod
    def search_decision_makers(self, hotel_name, website=None, brand=None, location=None):
        raise NotImplementedError


class PeopleEnrichmentError(Exception):
    """Base error for professional-contact providers."""


class PeopleEnrichmentConfigurationError(PeopleEnrichmentError):
    """Raised when a provider is not configured."""
