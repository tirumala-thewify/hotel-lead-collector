from django.urls import path

from .location_api import location_search


urlpatterns = [
    path('search/', location_search, name='location-search'),
]
