from django.db import models
from django.conf import settings
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def _fernet():
    digest = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


class ProviderSettings(models.Model):
    OPENSTREETMAP = 'openstreetmap'
    GEOAPIFY = 'geoapify'
    GOOGLE = 'google'
    HOTEL_PROVIDER_CHOICES = [
        (OPENSTREETMAP, 'OpenStreetMap'),
        (GEOAPIFY, 'Geoapify'),
        (GOOGLE, 'Google Places'),
    ]

    hotel_provider = models.CharField(
        max_length=20,
        choices=HOTEL_PROVIDER_CHOICES,
        default=OPENSTREETMAP,
    )
    business_providers = models.JSONField(default=list, blank=True)
    business_providers = models.JSONField(default=list, blank=True)
    google_api_key_encrypted = models.TextField(blank=True)
    geoapify_api_key_encrypted = models.TextField(blank=True)
    apollo_enabled = models.BooleanField(default=False)
    apollo_api_key_encrypted = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

    def _set_secret(self, field, value):
        setattr(self, field, _fernet().encrypt(value.encode()).decode() if value else '')

    def _get_secret(self, field):
        encrypted = getattr(self, field)
        if not encrypted:
            return ''
        try:
            return _fernet().decrypt(encrypted.encode()).decode()
        except InvalidToken:
            return ''

    def set_google_api_key(self, value):
        self._set_secret('google_api_key_encrypted', value)

    def get_google_api_key(self):
        return self._get_secret('google_api_key_encrypted')

    def set_geoapify_api_key(self, value):
        self._set_secret('geoapify_api_key_encrypted', value)

    def get_geoapify_api_key(self):
        return self._get_secret('geoapify_api_key_encrypted')

    def set_apollo_api_key(self, value):
        self._set_secret('apollo_api_key_encrypted', value)

    def get_apollo_api_key(self):
        return self._get_secret('apollo_api_key_encrypted')

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
