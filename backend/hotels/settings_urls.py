from django.urls import path

from .provider_settings_api import provider_settings_view


urlpatterns = [
    path('providers/', provider_settings_view, name='provider-settings'),
]
