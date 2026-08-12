from contextlib import contextmanager


class BrowserStartupError(Exception):
    """Raised when Playwright or Chromium cannot be started."""


@contextmanager
def browser_page(*, headless=True, timeout=15000):
    """Yield one isolated page and close every browser resource on exit."""
    manager = browser = context = page = None
    try:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserStartupError('Playwright or Chromium is not installed.') from exc
        manager = sync_playwright().start()
        browser = manager.chromium.launch(headless=headless)
        context = browser.new_context(locale='en-US')
        page = context.new_page()
        page.set_default_timeout(timeout)
        page.set_default_navigation_timeout(timeout)
        yield page
    except BrowserStartupError:
        raise
    except Exception as exc:
        if browser is None:
            raise BrowserStartupError('Chromium could not be started.') from exc
        raise
    finally:
        for resource in (page, context, browser):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    pass
        if manager is not None:
            try:
                manager.stop()
            except Exception:
                pass
