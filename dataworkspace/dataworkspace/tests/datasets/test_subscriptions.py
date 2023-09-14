import pytest
from django.conf import settings
from waffle.testutils import override_flag

from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.tests import factories


@pytest.mark.django_db
@override_flag(settings.NOTIFY_ON_MASTER_DATASET_CHANGE_FLAG, active=True)
def test_master_subscription_appears_when_flag_is_active(client):
    ds = factories.DataSetFactory.create(
        type=DataSetType.MASTER,
        published=True,
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    response = client.get(ds.get_absolute_url())
    assert response.status_code == 200
    assert "Get updates" in response.content.decode(response.charset)


@pytest.mark.django_db
@override_flag(settings.NOTIFY_ON_MASTER_DATASET_CHANGE_FLAG, active=False)
def test_master_subscription_hidden_when_flag_is_false(client):
    ds = factories.DataSetFactory.create(
        type=DataSetType.MASTER,
        published=True,
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    response = client.get(ds.get_absolute_url())
    assert response.status_code == 200
    assert "Get updates" not in response.content.decode(response.charset)


@pytest.mark.django_db
@override_flag(settings.NOTIFY_ON_DATACUT_CHANGE_FLAG, active=True)
def test_datacut_subscription_appears_when_flag_is_active(client):
    ds = factories.DataSetFactory.create(
        type=DataSetType.DATACUT,
        published=True,
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    response = client.get(ds.get_absolute_url())
    assert response.status_code == 200
    assert "Get updates" in response.content.decode(response.charset)


@pytest.mark.django_db
@override_flag(settings.NOTIFY_ON_DATACUT_CHANGE_FLAG, active=False)
def test_datacut_subscription_hidden_when_flag_is_false(client):
    ds = factories.DataSetFactory.create(
        type=DataSetType.DATACUT,
        published=True,
        user_access_type=UserAccessType.REQUIRES_AUTHORIZATION,
    )

    response = client.get(ds.get_absolute_url())
    assert response.status_code == 200
    assert "Get updates" not in response.content.decode(response.charset)


@pytest.mark.django_db
@override_flag(settings.NOTIFY_ON_REFERENCE_DATASET_CHANGE_FLAG, active=True)
def test_reference_dataset_subscription_appears_when_flag_is_active(client):
    ds = factories.ReferenceDatasetFactory.create(
        published=True,
    )

    response = client.get(ds.get_absolute_url())
    assert response.status_code == 200
    assert "Get updates" in response.content.decode(response.charset)


@pytest.mark.django_db
@override_flag(settings.NOTIFY_ON_REFERENCE_DATASET_CHANGE_FLAG, active=False)
def test_reference_dataset_subscription_hidden_when_flag_is_false(client):
    ds = factories.ReferenceDatasetFactory.create(
        published=True,
    )

    response = client.get(ds.get_absolute_url())
    assert response.status_code == 200
    assert "Get updates" not in response.content.decode(response.charset)
