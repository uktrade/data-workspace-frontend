import pytest
from django.conf import settings
from waffle.testutils import override_flag

from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.tests import factories


@pytest.mark.django_db
@override_flag(settings.NOTIFY_ON_DATASET_CHANGE_FLAG, active=True)
def test_subscription_appears_when_flag_is_active(client):
    ds = factories.DataSetFactory.create(
        type=DataSetType.MASTER,
        published=True,
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    response = client.get(ds.get_absolute_url())
    assert response.status_code == 200
    assert 'Get updated when this dataset changes' in response.content.decode(
        response.charset
    )


@pytest.mark.django_db
@override_flag(settings.NOTIFY_ON_DATASET_CHANGE_FLAG, active=False)
def test_subscription_hidden_when_flag_is_false(client):
    ds = factories.DataSetFactory.create(
        type=DataSetType.MASTER,
        published=True,
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    response = client.get(ds.get_absolute_url())
    assert response.status_code == 200
    assert 'Get updated when this dataset changes' not in response.content.decode(
        response.charset
    )
