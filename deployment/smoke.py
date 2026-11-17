"""Dependency-free post-deployment checks, executed on the Tentacle target."""
import json
import sys
import time
from urllib.request import urlopen


def check(base):
    with urlopen(base, timeout=10) as response:
        if 'id="root"' not in response.read().decode():
            raise ValueError('Frontend document missing')
    for endpoint in ['health', 'dashboard', 'movies', 'customers', 'rentals', 'actors', 'stores']:
        with urlopen(f'{base}/api/{endpoint}', timeout=10) as response:
            data = json.load(response)
        if endpoint == 'health':
            if data.get('database') != 'CONNECTED':
                raise ValueError('Database is not ready')
        elif endpoint == 'dashboard':
            if data.get('totalMovies', 0) < 1 or data.get('totalCustomers', 0) < 1:
                raise ValueError('Database is not seeded')
        elif not isinstance(data, list) or not data:
            raise ValueError(f'{endpoint} has no sample data')


if __name__ == '__main__':
    base = sys.argv[1].rstrip('/')
    for attempt in range(12):
        try:
            check(base)
            print('Frontend, database, dashboard, and all five lists passed smoke checks.')
            break
        except Exception as error:
            if attempt == 11:
                raise SystemExit(f'Smoke checks failed: {error}')
            time.sleep(5)
