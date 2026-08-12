import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse

import requests

from .base import EnrichmentError, HotelEnrichmentProvider
from .website_discovery import discover_official_website


USER_AGENT = 'HotelLeadCollector/0.1 (+hotel contact enrichment)'
REQUEST_TIMEOUT_SECONDS = 10
MAX_REDIRECTS = 3
MAX_PAGES = 3
MAX_RESPONSE_BYTES = 1_000_000
PAGE_LINK_MARKERS = {
    'contact': ('contact', 'contact-us', 'contact us', 'reach-us', 'reach us',
                'location', 'hotel-info', 'hotel info', 'reservations'),
    'about': ('about', 'about-us', 'about us', 'corporate'),
    'team': ('team', 'our-team', 'our team'),
    'leadership': ('leadership', 'executive', 'executives'),
    'management': ('management', 'managers'),
    'sales': (
        'sales', 'sales-team', 'corporate-sales', 'group-sales', 'meetings-sales',
        'events-sales', 'business-sales', 'contact-sales',
    ),
    'press': ('press', 'news', 'media'),
}
CONTACT_LINK_MARKERS = tuple(
    marker for markers in PAGE_LINK_MARKERS.values() for marker in markers
)
SALES_NEGATIVE_MARKERS = (
    'terms', 'conditions', 'terms and conditions', 'legal', 'policy', 'privacy',
    'sales conditions', 'internet sales conditions',
)
SOCIAL_DOMAINS = {
    'linkedin': 'linkedin.com',
    'facebook': 'facebook.com',
    'instagram': 'instagram.com',
}
SOCIAL_REJECTED_PATH_PARTS = {
    'linkedin': {'login', 'sharing', 'sharearticle', 'intent', 'oauth', 'checkpoint'},
    'facebook': {
        'login', 'login.php', 'sharer', 'sharer.php', 'share', 'share.php',
        'dialog', 'intent', 'plugins',
    },
    'instagram': {'accounts', 'login', 'share', 'oauth'},
}
SOCIAL_ALLOWED_PATH_PREFIXES = {
    'linkedin': {'company', 'in', 'school', 'showcase'},
}
BUSINESS_EMAIL_PREFIXES = {
    'info', 'reservations', 'reservation', 'sales', 'contact', 'frontoffice',
    'frontdesk', 'reception', 'booking', 'bookings', 'enquiries', 'inquiries',
}
EMAIL_PATTERN = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.IGNORECASE)
LABELLED_PHONE_PATTERN = re.compile(
    r'(?:phone|tel(?:ephone)?|call|reservations?)\s*[:\-]?\s*'
    r'(\+?[\d][\d\s().-]{6,}\d)',
    re.IGNORECASE,
)
ENRICHED_FIELDS = ('phone', 'email', 'address', 'brand')
CORE_CONTACT_FIELDS = ('phone', 'email', 'address')
REJECTED_EMAIL_PREFIXES = {'privacy', 'legal', 'webmaster', 'developer', 'support'}


class ContactPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.mailto = []
        self.tel = []
        self.json_ld = []
        self.addresses = []
        self.visible_text = []
        self._script_type = None
        self._script_parts = []
        self._address_depth = 0
        self._address_parts = []
        self._hidden_depth = 0
        self._anchor_href = None
        self._anchor_parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'a':
            href = (attributes.get('href') or '').strip()
            if href.startswith('mailto:'):
                self.mailto.append(href[7:].split('?', 1)[0])
            elif href.startswith('tel:'):
                self.tel.append(href[4:].split('?', 1)[0])
            elif href:
                self._anchor_href = href
                self._anchor_parts = []
        elif tag == 'script':
            self._script_type = (attributes.get('type') or '').lower()
            self._script_parts = []
            self._hidden_depth += 1
        elif tag == 'style':
            self._hidden_depth += 1
        elif tag == 'address':
            self._address_depth += 1

    def handle_endtag(self, tag):
        if tag == 'a':
            if self._anchor_href:
                self.links.append((self._anchor_href, ' '.join(self._anchor_parts)))
            self._anchor_href = None
            self._anchor_parts = []
        elif tag == 'script':
            if self._script_type == 'application/ld+json':
                self.json_ld.append(''.join(self._script_parts))
            self._script_type = None
            self._script_parts = []
            self._hidden_depth = max(0, self._hidden_depth - 1)
        elif tag == 'style':
            self._hidden_depth = max(0, self._hidden_depth - 1)
        elif tag == 'address':
            self._address_depth = max(0, self._address_depth - 1)
            address = ' '.join(' '.join(self._address_parts).split())
            if address:
                self.addresses.append(address)
            self._address_parts = []

    def handle_data(self, data):
        if self._script_type == 'application/ld+json':
            self._script_parts.append(data)
        if self._address_depth:
            self._address_parts.append(data)
        if not self._hidden_depth and data.strip():
            self.visible_text.append(data.strip())
        if self._anchor_href and data.strip():
            self._anchor_parts.append(data.strip())


def _is_blocked_ip(value):
    ip = ipaddress.ip_address(value)
    nat64_network = ipaddress.ip_network('64:ff9b::/96')
    if isinstance(ip, ipaddress.IPv6Address) and ip in nat64_network:
        return _is_blocked_ip(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
    return any((
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ))


def _validate_public_url(url):
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as exc:
        raise EnrichmentError('The website URL is invalid.') from exc

    if parsed.scheme not in {'http', 'https'}:
        raise EnrichmentError('Only HTTP and HTTPS website URLs are supported.')
    if not parsed.hostname or parsed.username or parsed.password:
        raise EnrichmentError('The website URL is invalid.')
    if port not in {None, 80, 443}:
        raise EnrichmentError('The website URL uses an unsupported port.')

    hostname = parsed.hostname.rstrip('.').lower()
    if hostname == 'localhost' or hostname.endswith('.localhost'):
        raise EnrichmentError('Local and private website addresses are not allowed.')

    try:
        literal_ip = ipaddress.ip_address(hostname)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        addresses = {str(literal_ip)}
    else:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(hostname, port or 443)}
        except socket.gaierror as exc:
            raise EnrichmentError('The website hostname could not be resolved.') from exc
    if not addresses or any(_is_blocked_ip(address) for address in addresses):
        raise EnrichmentError('Local and private website addresses are not allowed.')
    return url


def _read_limited_html(response):
    content_type = response.headers.get('Content-Type', '').lower()
    if 'text/html' not in content_type and 'application/xhtml+xml' not in content_type:
        raise EnrichmentError('The website did not return an HTML page.')
    chunks = []
    size = 0
    for chunk in response.iter_content(chunk_size=16_384):
        size += len(chunk)
        if size > MAX_RESPONSE_BYTES:
            raise EnrichmentError('The website response is too large.')
        chunks.append(chunk)
    encoding = response.encoding or 'utf-8'
    return b''.join(chunks).decode(encoding, errors='replace')


def _fetch_html(url):
    current_url = url
    for redirect_count in range(MAX_REDIRECTS + 1):
        _validate_public_url(current_url)
        try:
            response = requests.get(
                current_url,
                headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'},
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
                stream=True,
            )
        except requests.Timeout as exc:
            raise EnrichmentError('The hotel website request timed out.') from exc
        except requests.ConnectionError as exc:
            raise EnrichmentError('Could not connect to the hotel website.') from exc
        except requests.RequestException as exc:
            raise EnrichmentError('The hotel website request failed.') from exc

        if response.is_redirect or response.is_permanent_redirect:
            if redirect_count == MAX_REDIRECTS:
                raise EnrichmentError('The hotel website redirected too many times.')
            location = response.headers.get('Location')
            if not location:
                raise EnrichmentError('The hotel website returned an invalid redirect.')
            current_url = urljoin(current_url, location)
            continue
        if response.status_code != 200:
            raise EnrichmentError(
                f'The hotel website returned HTTP {response.status_code}.'
            )
        return current_url, _read_limited_html(response)
    raise EnrichmentError('The hotel website redirected too many times.')


def _business_email(value, allowed_domain=None, allow_domain_email=False):
    value = value.strip().lower()
    if not EMAIL_PATTERN.fullmatch(value):
        return None
    local_part, domain = value.rsplit('@', 1)
    if local_part in REJECTED_EMAIL_PREFIXES:
        return None
    if local_part in BUSINESS_EMAIL_PREFIXES:
        return value
    if allow_domain_email and allowed_domain:
        allowed_domain = allowed_domain.removeprefix('www.').lower()
        if domain == allowed_domain or domain.endswith(f'.{allowed_domain}'):
            return value
    return None


def _address_from_json_ld(value):
    if isinstance(value, str):
        return ' '.join(value.split()) or None
    if not isinstance(value, dict):
        return None
    parts = [value.get(key) for key in (
        'streetAddress', 'addressLocality', 'addressRegion', 'postalCode', 'addressCountry'
    )]
    return ', '.join(str(part).strip() for part in parts if part) or None


def _json_ld_entities(value):
    if isinstance(value, list):
        for item in value:
            yield from _json_ld_entities(item)
    elif isinstance(value, dict):
        yield value
        if '@graph' in value:
            yield from _json_ld_entities(value['@graph'])


def _extract_contacts(html, allowed_domain=None, allow_domain_email=False):
    parser = ContactPageParser()
    parser.feed(html)
    result = {'phone': None, 'email': None, 'address': None, 'brand': None, 'url': None}

    for block in parser.json_ld:
        try:
            data = json.loads(block)
        except (TypeError, ValueError):
            continue
        for entity in _json_ld_entities(data):
            entity_types = entity.get('@type', [])
            if isinstance(entity_types, str):
                entity_types = [entity_types]
            if not {'Hotel', 'Organization', 'LodgingBusiness', 'LocalBusiness'}.intersection(entity_types):
                continue
            result['phone'] = result['phone'] or entity.get('telephone')
            result['email'] = result['email'] or entity.get('email')
            result['address'] = result['address'] or _address_from_json_ld(entity.get('address'))
            result['url'] = result['url'] or entity.get('url')
            brand = entity.get('brand')
            if isinstance(brand, dict):
                brand = brand.get('name')
            result['brand'] = result['brand'] or brand

    result['phone'] = result['phone'] or next((value.strip() for value in parser.tel if value.strip()), None)
    result['email'] = result['email'] or next(
        (email for value in parser.mailto
         if (email := _business_email(value, allowed_domain, allow_domain_email))), None
    )
    result['address'] = result['address'] or next(iter(parser.addresses), None)

    visible_text = ' '.join(parser.visible_text)
    if not result['phone']:
        phone_match = LABELLED_PHONE_PATTERN.search(visible_text)
        result['phone'] = phone_match.group(1).strip() if phone_match else None
    if not result['email']:
        result['email'] = next(
            (email for value in EMAIL_PATTERN.findall(visible_text)
            if (email := _business_email(value, allowed_domain, allow_domain_email))),
            None,
        )
    return result, parser.links


def _page_category(path, anchor_text):
    haystack = re.sub(
        r'[^a-z0-9]+', ' ', f'{path} {anchor_text}'.casefold()
    ).strip()
    sales_markers = tuple(
        marker.replace('-', ' ') for marker in PAGE_LINK_MARKERS['sales']
    )
    if not any(marker in haystack for marker in SALES_NEGATIVE_MARKERS):
        tokens = set(haystack.split())
        if 'sales' in tokens or any(
            marker != 'sales' and marker in haystack for marker in sales_markers
        ):
            return 'sales'
    for category, markers in PAGE_LINK_MARKERS.items():
        if category == 'sales':
            continue
        normalized_markers = tuple(marker.replace('-', ' ') for marker in markers)
        if any(marker in haystack for marker in normalized_markers):
            return category
    return None


def _discover_pages(base_url, links):
    base_host = (urlparse(base_url).hostname or '').lower()
    candidates = []
    discovered = {category: None for category in PAGE_LINK_MARKERS}
    for link, anchor_text in links:
        absolute = urljoin(base_url, link)
        parsed = urlparse(absolute)
        if (parsed.hostname or '').lower() != base_host:
            continue
        category = _page_category(parsed.path, anchor_text)
        if not category:
            continue
        normalized = urlunparse(parsed._replace(fragment=''))
        discovered[category] = discovered[category] or normalized
        priority = list(PAGE_LINK_MARKERS).index(category)
        if all(candidate[1] != normalized for candidate in candidates):
            candidates.append((priority, normalized))
    candidates.sort(key=lambda candidate: candidate[0])
    return discovered, [url for _, url in candidates[: MAX_PAGES - 1]]


def _social_profile_url(value):
    try:
        parsed = urlparse(value)
        port = parsed.port
    except (TypeError, ValueError):
        return None, None
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or port not in {None, 80, 443}:
        return None, None
    if parsed.username or parsed.password:
        return None, None
    hostname = parsed.hostname.casefold().rstrip('.')
    platform = next((
        name for name, domain in SOCIAL_DOMAINS.items()
        if hostname == domain or hostname.endswith(f'.{domain}')
    ), None)
    if not platform:
        return None, None
    path_parts = [part.casefold() for part in parsed.path.split('/') if part]
    if not path_parts or any(
        part in SOCIAL_REJECTED_PATH_PARTS[platform] for part in path_parts
    ):
        return None, None
    allowed_prefixes = SOCIAL_ALLOWED_PATH_PREFIXES.get(platform)
    if allowed_prefixes and path_parts[0] not in allowed_prefixes:
        return None, None
    normalized_path = parsed.path.rstrip('/') or '/'
    normalized = urlunparse(('https', hostname, normalized_path, '', parsed.query, ''))
    return platform, normalized


def _extract_social_profiles(base_url, links):
    profiles = {platform: None for platform in SOCIAL_DOMAINS}
    for link, _anchor_text in links:
        platform, profile_url = _social_profile_url(urljoin(base_url, link))
        if platform and not profiles[platform]:
            profiles[platform] = profile_url
    return profiles


class HotelWebsiteEnrichmentProvider(HotelEnrichmentProvider):
    def enrich(self, hotel):
        discovery = discover_official_website(
            hotel_name=hotel.get('name'),
            address=hotel.get('address'),
            brand=hotel.get('brand'),
            latitude=hotel.get('latitude'),
            longitude=hotel.get('longitude'),
            website=hotel.get('website'),
            contact_website=hotel.get('contact_website'),
            brand_website=hotel.get('brand_website'),
            domain_hint=hotel.get('domain_hint'),
            wikidata=hotel.get('wikidata'),
            wikipedia=hotel.get('wikipedia'),
            source=hotel.get('source'),
        )
        website = discovery['website']
        if not website:
            return {
                'hotel_name': hotel.get('name'),
                'website': None,
                'phone': None,
                'email': None,
                'address': None,
                'brand': None,
                'source_urls': [],
                'discovered_pages': {category: None for category in PAGE_LINK_MARKERS},
                'social_profiles': {platform: None for platform in SOCIAL_DOMAINS},
                'social_profile_sources': {platform: None for platform in SOCIAL_DOMAINS},
                'sources': {'website': None, 'phone': None, 'email': None, 'address': None, 'brand': None},
                'website_confidence': discovery.get('confidence'),
                'status': 'NOT_FOUND',
                'message': 'No official website is available for enrichment.',
            }

        _validate_public_url(website)
        result = {
            'hotel_name': hotel.get('name'),
            'website': website,
            'phone': None,
            'email': None,
            'address': None,
            'brand': None,
            'source_urls': [],
            'discovered_pages': {category: None for category in PAGE_LINK_MARKERS},
            'social_profiles': {platform: None for platform in SOCIAL_DOMAINS},
            'social_profile_sources': {platform: None for platform in SOCIAL_DOMAINS},
            'sources': {
                'website': discovery['source'],
                'phone': None,
                'email': None,
                'address': None,
                'brand': None,
            },
            'website_confidence': discovery.get('confidence'),
            'status': 'NOT_STARTED',
        }

        final_home_url, home_html = _fetch_html(website)
        pages = [(final_home_url, home_html)]
        website_domain = (urlparse(final_home_url).hostname or '').removeprefix('www.')
        _, home_links = _extract_contacts(home_html, allowed_domain=website_domain)
        result['discovered_pages'], page_urls = _discover_pages(final_home_url, home_links)
        for page_url in page_urls:
            try:
                pages.append(_fetch_html(page_url))
            except EnrichmentError:
                # Optional pages must not discard data already obtained from the
                # homepage or another successfully fetched same-domain page.
                continue

        for source_url, html in pages:
            page_path = urlparse(source_url).path.lower()
            is_contact_page = any(
                marker.replace(' ', '-') in page_path.replace('_', '-')
                for marker in CONTACT_LINK_MARKERS
            )
            contacts, links = _extract_contacts(
                html,
                allowed_domain=website_domain,
                allow_domain_email=is_contact_page,
            )
            found_on_page = False
            for field in ENRICHED_FIELDS:
                if not result[field] and contacts[field]:
                    result[field] = contacts[field]
                    result['sources'][field] = source_url
                    found_on_page = True
            social_profiles = _extract_social_profiles(source_url, links)
            for platform, profile_url in social_profiles.items():
                if profile_url and not result['social_profiles'][platform]:
                    result['social_profiles'][platform] = profile_url
                    result['social_profile_sources'][platform] = source_url
                    found_on_page = True
            if found_on_page:
                if source_url not in result['source_urls']:
                    result['source_urls'].append(source_url)

        found_count = sum(bool(result[field]) for field in CORE_CONTACT_FIELDS)
        if found_count == len(CORE_CONTACT_FIELDS):
            result['status'] = 'FOUND'
        elif found_count:
            result['status'] = 'PARTIAL'
        else:
            result['status'] = 'NOT_FOUND'
        return result


def enrich_hotel_from_website(hotel):
    return HotelWebsiteEnrichmentProvider().enrich(hotel)
