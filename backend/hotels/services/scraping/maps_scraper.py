import logging
from urllib.parse import quote_plus

from django.conf import settings

from .browser import BrowserStartupError, browser_page
from .parsers import deduplicate_listings, listing_identity, normalize_listing


logger = logging.getLogger(__name__)
MAPS_SEARCH_URL = 'https://www.google.com/maps/search/{query}/@{latitude},{longitude},13z'
SELECTORS = {
    'feed': '[role="feed"]', 'card': '[role="feed"] > div:has(a[href*="/maps/place/"])',
    'card_link': 'a[href*="/maps/place/"]', 'rating': '[role="img"][aria-label*="star"]',
    'no_results': '[role="main"]',
}
DETAIL_SELECTORS = {
    'address': ('button[data-item-id="address"]', '[aria-label^="Address:"]'),
    'phone': ('button[data-item-id^="phone:"]', '[aria-label^="Phone:"]'),
    'website': ('a[data-item-id="authority"]', 'a[aria-label^="Website:"]'),
    'opening_hours': ('button[data-item-id="oh"]', '[aria-label*="hours" i]'),
    'review_count': (
        'button[jsaction*="rating.moreReviews"]',
        'button[aria-label*="review" i]',
    ),
}
DETAIL_READY_TIMEOUT_MS = 2_000


class ScraperError(Exception):
    """Controlled browser-search provider failure."""


class MapsScraper:
    def __init__(self, page_factory=browser_page):
        self.page_factory = page_factory

    def search(self, *, query, latitude, longitude, category, max_results=None):
        limit = max_results or settings.PLAYWRIGHT_MAX_RESULTS
        url = MAPS_SEARCH_URL.format(query=quote_plus(query), latitude=latitude, longitude=longitude)
        try:
            with self.page_factory(headless=settings.PLAYWRIGHT_HEADLESS, timeout=settings.PLAYWRIGHT_TIMEOUT) as page:
                page.goto(url, wait_until='domcontentloaded')
                feed = page.locator(SELECTORS['feed'])
                try:
                    feed.wait_for(state='visible')
                except Exception as exc:
                    if page.get_by_text('No results found', exact=False).count():
                        return []
                    raise exc
                self._collect_cards(page, feed, limit)
                return self._extract_results(page, category, limit)
        except BrowserStartupError as exc:
            raise ScraperError(str(exc)) from exc
        except Exception as exc:
            if exc.__class__.__name__ == 'TimeoutError':
                raise ScraperError('Business search page timed out.') from exc
            raise ScraperError('Business search page could not be processed.') from exc

    def search_many(
        self, *, queries, latitude, longitude, category,
        max_results_per_query=None, max_total_results=None,
    ):
        per_query_limit = max_results_per_query or settings.PLAYWRIGHT_MAX_RESULTS_PER_QUERY
        total_limit = max_total_results or settings.PLAYWRIGHT_MAX_TOTAL_RESULTS
        raw_listings, query_results, seen_identities = [], {}, set()
        try:
            with self.page_factory(
                headless=settings.PLAYWRIGHT_HEADLESS, timeout=settings.PLAYWRIGHT_TIMEOUT
            ) as page:
                for query in queries:
                    try:
                        cards = self._search_cards(
                            page, query, latitude, longitude, per_query_limit
                        )
                        raw_listings.extend(cards)
                        unique_added = 0
                        for card in cards:
                            identity = listing_identity(card)
                            if identity not in seen_identities:
                                seen_identities.add(identity)
                                unique_added += 1
                        query_results[query] = {
                            'status': 'success', 'count': len(cards),
                            'unique_added': unique_added,
                        }
                    except Exception:
                        logger.info('Browser category query failed: %s', query, exc_info=True)
                        query_results[query] = {
                            'status': 'error', 'count': 0, 'unique_added': 0,
                        }
                if not any(item['status'] == 'success' for item in query_results.values()):
                    raise ScraperError('All browser category queries failed.')
                unique_raw = self._deduplicate_raw_listings(raw_listings)[:total_limit]
                results = self._extract_raw_results(page, unique_raw, category)
        except BrowserStartupError as exc:
            raise ScraperError(str(exc)) from exc
        except ScraperError:
            raise
        except Exception as exc:
            raise ScraperError('Business search page could not be processed.') from exc
        self.last_query_results = query_results
        self.last_search_counts = {
            'combined': len(raw_listings), 'unique': len(unique_raw),
            'returned': len(results),
        }
        return results[:total_limit]

    def _search_cards(self, page, query, latitude, longitude, limit):
        url = MAPS_SEARCH_URL.format(
            query=quote_plus(query), latitude=latitude, longitude=longitude
        )
        page.goto(url, wait_until='domcontentloaded')
        feed = page.locator(SELECTORS['feed'])
        try:
            feed.wait_for(state='visible')
        except Exception:
            if page.get_by_text('No results found', exact=False).count():
                return []
            raise
        self._collect_cards(page, feed, limit)
        return self._extract_raw_cards(page, limit)

    def _extract_raw_cards(self, page, limit):
        raw_listings, cards = [], page.locator(SELECTORS['card'])
        for index in range(min(cards.count(), limit)):
            try:
                card = cards.nth(index)
                link = card.locator(SELECTORS['card_link']).first
                raw_listings.append({
                    'name': link.get_attribute('aria-label'),
                    'maps_url': link.get_attribute('href'),
                    'rating': self._attribute(card, SELECTORS['rating'], 'aria-label'),
                    'review_count': card.inner_text(),
                })
            except Exception:
                logger.info('Skipping a listing card that could not be parsed.', exc_info=True)
        return raw_listings

    @staticmethod
    def _deduplicate_raw_listings(raw_listings):
        unique, keys = [], set()
        for raw in raw_listings:
            key = listing_identity(raw)
            if key not in keys:
                keys.add(key)
                unique.append(raw)
        return unique

    def _extract_raw_results(self, page, raw_listings, category):
        results = []
        for raw in raw_listings:
            try:
                try:
                    self.open_listing(page, raw['maps_url'])
                    raw.update(self.extract_listing_details(page))
                except Exception:
                    logger.info('Listing details were unavailable; keeping card data.', exc_info=True)
                normalized = normalize_listing(raw, category)
                if normalized:
                    results.append(normalized)
            except Exception:
                logger.info('Skipping a listing that could not be parsed.', exc_info=True)
        return deduplicate_listings(results)

    def _collect_cards(self, page, feed, limit):
        previous = -1
        for _ in range(8):
            count = page.locator(SELECTORS['card']).count()
            if count >= limit or count == previous:
                break
            previous = count
            feed.evaluate('(element) => element.scrollBy(0, element.scrollHeight)')
            page.wait_for_timeout(400)

    def _extract_results(self, page, category, limit):
        return self._extract_raw_results(
            page, self._extract_raw_cards(page, limit), category
        )[:limit]

    def open_listing(self, page, maps_url):
        page.goto(maps_url, wait_until='domcontentloaded')
        page.locator('h1').first.wait_for(state='visible')
        ready_selector = ', '.join(
            selector for selectors in DETAIL_SELECTORS.values() for selector in selectors
        )
        try:
            page.locator(ready_selector).first.wait_for(
                state='attached', timeout=DETAIL_READY_TIMEOUT_MS,
            )
        except Exception:
            # A valid listing can legitimately expose none of these optional fields.
            pass

    def extract_listing_details(self, page):
        return {
            'address': self._first_attribute(page, DETAIL_SELECTORS['address'], 'aria-label'),
            'phone': self._first_attribute(page, DETAIL_SELECTORS['phone'], 'aria-label'),
            'website': self._first_attribute(page, DETAIL_SELECTORS['website'], 'href'),
            'opening_hours': self._first_attribute(
                page, DETAIL_SELECTORS['opening_hours'], 'aria-label'
            ),
            'review_count': self._first_attribute(
                page, DETAIL_SELECTORS['review_count'], 'aria-label'
            ),
        }

    @classmethod
    def _first_attribute(cls, scope, selectors, attribute):
        for selector in selectors:
            value = cls._attribute(scope, selector, attribute)
            if value:
                return value
        return None

    @staticmethod
    def _attribute(scope, selector, attribute):
        locator = scope.locator(selector)
        return locator.first.get_attribute(attribute) if locator.count() else None
