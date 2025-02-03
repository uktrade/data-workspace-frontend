import mock
import pytest
from django.conf import settings

from arango import ArangoClient
from dataworkspace.apps.arangodb.models import ArangoUser
from dataworkspace.apps.arangodb.utils import (
    delete_unused_arangodb_users,
    new_private_arangodb_credentials,
)
from dataworkspace.apps.core.utils import postgres_user
from dataworkspace.tests.core.factories import TeamFactory, TeamMembershipFactory
from dataworkspace.tests.factories import UserFactory


class TestDeleteUnusedArangoUsers:
    @pytest.mark.django_db(transaction=True)
    def test_deletes_expired_arango_users(self):
        user = UserFactory(email="test@foo.bar")
        team = TeamFactory(platform="postgres-and-arango")
        _ = TeamMembershipFactory(team=team, user=user)
        user_count = ArangoUser.objects.count()

        database_data = settings.ARANGODB
        client = ArangoClient(hosts=f"http://{database_data['HOST']}:{database_data['PORT']}")
        sys_db = client.db("_system", username="root", password=database_data["PASSWORD"])

        user_creds_to_drop = new_private_arangodb_credentials(
            postgres_user(user.email),
            user,
        )
        assert ArangoUser.objects.count() == user_count + 1
        assert user_creds_to_drop["ARANGO_USER"] in [u["username"] for u in sys_db.users()]

        with mock.patch("dataworkspace.apps.applications.utils.gevent.sleep"):
            delete_unused_arangodb_users()

        assert (
            ArangoUser.objects.get(username=user_creds_to_drop["ARANGO_USER"]).deleted_date
            is not None
        )
        assert user_creds_to_drop["ARANGO_USER"] not in [u["username"] for u in sys_db.users()]
