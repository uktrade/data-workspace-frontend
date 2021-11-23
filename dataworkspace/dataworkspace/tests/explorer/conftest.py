import pytest
from django.conf import settings

from dataworkspace.apps.core.models import Database


@pytest.fixture(scope="function", autouse=True)
def ensure_databases_configured(db):
    # From dataworkspace/dataworkspace/apps/datasets/management/commands/ensure_databases_configured.py
    for database_name, _ in settings.DATABASES_DATA.items():
        Database.objects.get_or_create(memorable_name=database_name)
