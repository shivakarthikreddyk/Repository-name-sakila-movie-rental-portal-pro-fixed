from playwright.sync_api import expect


def test_navigation_search_and_empty_state(page, portal_url):
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(portal_url)
    expect(page.get_by_text('Total Movies', exact=True)).to_be_visible()
    expect(page.locator('.card').first).to_contain_text('1000')
    for tab in ['movies', 'customers', 'rentals', 'actors', 'stores']:
        page.get_by_role('button', name=tab, exact=True).click()
        expect(page.locator('tbody tr').first).to_be_visible()
        expect(page.get_by_role('alert')).to_have_count(0)
    page.get_by_role('button', name='movies', exact=True).click()
    search = page.get_by_role('textbox', name='Search movies')
    search.fill('ACADEMY DINOSAUR')
    search.press('Enter')
    expect(page.locator('tbody tr')).to_have_count(1)
    expect(page.locator('tbody')).to_contain_text('ACADEMY DINOSAUR')
    search.fill('does-not-exist-928471')
    page.get_by_role('button', name='Search', exact=True).click()
    expect(page.get_by_text('No records found.', exact=True)).to_be_visible()
    page.get_by_role('button', name='customers', exact=True).click()
    expect(page.get_by_role('textbox', name='Search customers')).to_have_value('')
    expect(page.locator('tbody tr').first).to_be_visible()
    assert errors == []


def test_mobile_navigation(page, portal_url):
    page.set_viewport_size({'width': 390, 'height': 844})
    page.goto(portal_url)
    expect(page.get_by_text('Total Movies', exact=True)).to_be_visible()
    page.get_by_role('button', name='movies', exact=True).click()
    expect(page.locator('tbody tr').first).to_be_visible()
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')


def test_failed_api_shows_error_and_navigation_recovers(page, portal_url):
    page.route('**/api/movies', lambda route: route.fulfill(status=503, json={'error': 'Unavailable'}))
    page.goto(portal_url)
    page.get_by_role('button', name='movies', exact=True).click()
    expect(page.get_by_role('alert')).to_contain_text('Unable to load movies')
    expect(page.get_by_text('No records found.', exact=True)).to_have_count(0)
    page.get_by_role('button', name='customers', exact=True).click()
    expect(page.locator('tbody tr').first).to_be_visible()
    expect(page.get_by_role('alert')).to_have_count(0)
