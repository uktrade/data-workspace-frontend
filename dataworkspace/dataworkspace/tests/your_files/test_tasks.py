from datetime import datetime

import mock
import pytest

from dataworkspace.apps.core.utils import get_s3_prefix
from dataworkspace.apps.your_files.tasks import _collect_your_files_stats
from dataworkspace.tests import factories


@pytest.mark.django_db
@mock.patch("dataworkspace.apps.core.boto3_client.boto3.client")
def test_collect_your_files_stats(mock_client):
    user = factories.UserFactory.create()
    user.profile.sso_status = "active"
    user.profile.first_login = datetime.now()
    user.profile.save()

    mock_client.return_value.get_paginator.return_value.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": f"{get_s3_prefix(str(user.profile.sso_id))}bigdata/test",
                    "Size": 10,
                },
                {
                    "Key": f"{get_s3_prefix(str(user.profile.sso_id))}/test",
                    "Size": 10,
                },
            ]
        },
    ]

    _collect_your_files_stats()
    assert user.your_files_stats.count() == 1
    assert user.your_files_stats.latest().total_size_bytes == 10
