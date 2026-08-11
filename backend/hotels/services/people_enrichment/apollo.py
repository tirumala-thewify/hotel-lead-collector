import re
from urllib.parse import urlparse

import requests
from django.conf import settings

from .base import (
    PeopleEnrichmentConfigurationError,
    PeopleEnrichmentError,
    PeopleEnrichmentProvider,
)


ORGANIZATION_SEARCH_URL = 'https://api.apollo.io/api/v1/mixed_companies/search'
PEOPLE_SEARCH_URL = 'https://api.apollo.io/api/v1/mixed_people/api_search'
PERSON_ENRICH_URL = 'https://api.apollo.io/api/v1/people/match'
REQUEST_TIMEOUT_SECONDS = 15
MAX_CONTACTS = 3

TITLE_DEPARTMENTS = {
    'general manager': 'General Management',
    'marketing manager': 'Marketing',
    'director of marketing': 'Marketing',
    'head of marketing': 'Marketing',
    'it manager': 'Information Technology',
    'it head': 'Information Technology',
    'head of it': 'Information Technology',
    'director of it': 'Information Technology',
    'information technology manager': 'Information Technology',
    'director of sales': 'Sales / Commercial',
    'director of sales marketing': 'Sales / Commercial',
    'commercial director': 'Sales / Commercial',
}
SEARCH_TITLES = [
    'General Manager', 'Marketing Manager', 'Director of Marketing',
    'Head of Marketing', 'IT Manager', 'IT Head', 'Head of IT',
    'Director of IT', 'Information Technology Manager', 'Director of Sales',
    'Director of Sales & Marketing', 'Commercial Director',
]
DEPARTMENT_PRIORITY = {
    'General Management': 0,
    'Marketing': 1,
    'Information Technology': 2,
    'Sales / Commercial': 3,
}


def _normalize(value):
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', (value or '').casefold()).split())


def _domain(website):
    if not website:
        return None
    hostname = urlparse(website).hostname
    return hostname.removeprefix('www.') if hostname else None


def _headers(api_key):
    return {'Accept': 'application/json', 'X-Api-Key': api_key}


def _request_json(url, api_key, params):
    try:
        response = requests.post(
            url,
            headers=_headers(api_key),
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise PeopleEnrichmentError('The Apollo request timed out.') from exc
    except requests.RequestException as exc:
        raise PeopleEnrichmentError('Could not connect to Apollo.') from exc
    if response.status_code != 200:
        raise PeopleEnrichmentError(
            f'Apollo returned HTTP {response.status_code}.'
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise PeopleEnrichmentError('Apollo returned invalid JSON.') from exc
    if not isinstance(data, dict):
        raise PeopleEnrichmentError('Apollo returned a malformed response.')
    return data


class ApolloPeopleEnrichmentProvider(PeopleEnrichmentProvider):
    def __init__(self, api_key=None):
        self.api_key = api_key if api_key is not None else settings.APOLLO_API_KEY
        if not self.api_key:
            raise PeopleEnrichmentConfigurationError('APOLLO_API_KEY is not configured.')

    def match_organization(self, hotel_name, website=None, brand=None, location=None):
        domain = _domain(website)
        params = {'page': 1, 'per_page': 5}
        if domain:
            params['q_organization_domains_list[]'] = domain
        else:
            params['q_organization_name'] = brand or hotel_name
        if location:
            params['organization_locations[]'] = location

        data = _request_json(ORGANIZATION_SEARCH_URL, self.api_key, params)
        organizations = data.get('organizations')
        if not isinstance(organizations, list):
            raise PeopleEnrichmentError('Apollo returned a malformed organization response.')

        for organization in organizations:
            if not isinstance(organization, dict):
                continue
            organization_domain = (organization.get('primary_domain') or organization.get('website_url') or '')
            organization_domain = _domain(organization_domain) or organization_domain.removeprefix('www.')
            if domain and organization_domain == domain:
                return organization
            if not domain and _normalize(organization.get('name')) in {
                _normalize(hotel_name), _normalize(brand)
            }:
                return organization
        return None

    def search_people(self, organization_id, domain=None, location=None):
        params = {
            'organization_ids[]': organization_id,
            'person_titles[]': SEARCH_TITLES,
            'include_similar_titles': 'false',
            'page': 1,
            'per_page': 10,
        }
        if domain:
            params['q_organization_domains_list[]'] = domain
        if location:
            params['person_locations[]'] = location
        data = _request_json(PEOPLE_SEARCH_URL, self.api_key, params)
        people = data.get('people')
        if not isinstance(people, list):
            raise PeopleEnrichmentError('Apollo returned a malformed people response.')
        return people

    def _select_people(self, people):
        best_by_department = {}
        for person in people:
            if not isinstance(person, dict):
                continue
            normalized_title = _normalize(person.get('title'))
            department = TITLE_DEPARTMENTS.get(normalized_title)
            if not department or department in best_by_department:
                continue
            best_by_department[department] = person
        return sorted(
            best_by_department.values(),
            key=lambda person: DEPARTMENT_PRIORITY[TITLE_DEPARTMENTS[_normalize(person.get('title'))]],
        )[:MAX_CONTACTS]

    def enrich_person(self, person, organization_name, domain=None):
        params = {
            'id': person.get('id'),
            'name': person.get('name'),
            'organization_name': organization_name,
            'domain': domain,
            'reveal_personal_emails': 'false',
            'reveal_phone_number': 'false',
        }
        params = {key: value for key, value in params.items() if value}
        data = _request_json(PERSON_ENRICH_URL, self.api_key, params)
        enriched = data.get('person')
        if enriched is None:
            enriched = person
        if not isinstance(enriched, dict):
            raise PeopleEnrichmentError('Apollo returned a malformed person response.')
        return enriched

    def _normalize_contact(self, person, fallback, organization_name):
        title = person.get('title') or fallback.get('title')
        department = TITLE_DEPARTMENTS.get(_normalize(title))
        if not department:
            return None

        phone = None
        for phone_record in person.get('phone_numbers') or []:
            if isinstance(phone_record, dict) and phone_record.get('type') in {'work', 'work_direct'}:
                phone = phone_record.get('sanitized_number') or phone_record.get('raw_number')
                if phone:
                    break
        return {
            'name': person.get('name') or fallback.get('name'),
            'title': title,
            'department': department,
            'company': (person.get('organization') or {}).get('name') or organization_name,
            'email': person.get('email'),
            'phone': phone,
            'linkedin_url': person.get('linkedin_url'),
            'source': 'Apollo',
            'verification_status': 'FOUND',
        }

    def search_decision_makers(self, hotel_name, website=None, brand=None, location=None):
        organization = self.match_organization(hotel_name, website, brand, location)
        if not organization or not organization.get('id'):
            return {'hotel_name': hotel_name, 'contacts': [], 'status': 'NOT_FOUND'}

        domain = _domain(website)
        candidates = self._select_people(
            self.search_people(organization['id'], domain, location)
        )
        contacts = []
        for candidate in candidates:
            enriched = self.enrich_person(candidate, organization.get('name') or hotel_name, domain)
            contact = self._normalize_contact(
                enriched, candidate, organization.get('name') or hotel_name
            )
            if contact:
                contacts.append(contact)
        return {
            'hotel_name': hotel_name,
            'contacts': contacts,
            'status': 'FOUND' if contacts else 'NOT_FOUND',
        }


def search_decision_makers(
    hotel_name, website=None, brand=None, location=None, api_key=None
):
    return ApolloPeopleEnrichmentProvider(api_key=api_key).search_decision_makers(
        hotel_name, website, brand, location
    )
