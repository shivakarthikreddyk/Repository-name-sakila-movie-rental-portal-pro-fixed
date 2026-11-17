import os
import pytest


@pytest.fixture(scope='session')
def portal_url():
    return os.environ.get('SAKILA_BASE_URL', 'http://127.0.0.1:8092').rstrip('/')
