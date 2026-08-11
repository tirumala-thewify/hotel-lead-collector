from django.urls import path

from .views import (
    enrich_hotel, enrich_hotels_bulk_api, enrich_managers,
    business_categories, enrich_managers_bulk_api, health, nearby_hotels,
)
from .export_api import export_excel


urlpatterns = [
    path('health/', health, name='health'),
    path('nearby/', nearby_hotels, name='nearby-hotels'),
    path('categories/', business_categories, name='business-categories'),
    path('enrich/', enrich_hotel, name='enrich-hotel'),
    path('enrich/bulk/', enrich_hotels_bulk_api, name='enrich-hotels-bulk'),
    path('enrich-managers/', enrich_managers, name='enrich-managers'),
    path('enrich-managers/bulk/', enrich_managers_bulk_api, name='enrich-managers-bulk'),
    path('export/excel/', export_excel, name='export-excel'),
]
