"""Exercise the real Nginx -> Express -> MySQL path. No API/database mocks."""
import re
import pytest
import requests


def get_json(base, path):
    response = requests.get(f'{base}/api/{path}', timeout=15)
    response.raise_for_status()
    return response.json()


def test_frontend_assets_and_database_readiness(portal_url):
    response = requests.get(portal_url, timeout=15)
    response.raise_for_status()
    assert '<div id="root"></div>' in response.text
    assets = re.findall(r'(?:src|href)="(/assets/[^\"]+)"', response.text)
    assert assets
    for asset in assets:
        result = requests.get(f'{portal_url}{asset}', timeout=15)
        assert result.status_code == 200
        assert 'text/html' not in result.headers['Content-Type']
    assert get_json(portal_url, 'health')['database'] == 'CONNECTED'


def test_dashboard_has_full_sakila_data(portal_url):
    data = get_json(portal_url, 'dashboard')
    assert data['totalMovies'] == 1000
    assert data['totalCustomers'] == 599
    assert data['totalRentals'] == 16044
    assert data['totalRevenue'] > 60000
    assert len(data['topMovies']) == 8
    assert data['monthlyRevenue']


@pytest.mark.parametrize('endpoint,key', [
    ('movies', 'title'), ('customers', 'email'), ('rentals', 'customer'),
    ('actors', 'film_count'), ('stores', 'manager'),
])
def test_all_list_endpoints(portal_url, endpoint, key):
    data = get_json(portal_url, endpoint)
    assert 0 < len(data) <= 100
    assert key in data[0]


@pytest.mark.parametrize('endpoint,search,field', [
    ('movies', 'ACADEMY', 'title'), ('customers', 'MARY', 'first_name'),
    ('rentals', 'ACADEMY', 'title'), ('actors', 'PENELOPE', 'first_name'),
    ('stores', 'Mike', 'manager'),
])
def test_search_filters_every_list(portal_url, endpoint, search, field):
    data = get_json(portal_url, f'{endpoint}?search={search}')
    assert data
    assert all(search.upper() in str(row[field]).upper() for row in data)


def test_rating_validation_empty_results_and_unknown_routes(portal_url):
    movies = get_json(portal_url, 'movies?rating=PG')
    assert movies and all(row['rating'] == 'PG' for row in movies)
    assert get_json(portal_url, 'movies?search=does-not-exist-928471') == []
    assert requests.get(f'{portal_url}/api/movies?rating=invalid', timeout=15).status_code == 400
    assert requests.get(f'{portal_url}/api/unknown', timeout=15).status_code == 404
