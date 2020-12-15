import datetime
import time

import mock
import pytest
from django.db import connections

from dataworkspace.apps.applications.utils import delete_unused_datasets_users
from dataworkspace.apps.core.utils import (
    source_tables_for_user,
    db_role_schema_suffix_for_user,
    new_private_database_credentials,
    postgres_user,
)
from dataworkspace.apps.datasets.management.commands.ensure_databases_configured import (
    Command as ensure_databases_configured,
)
from dataworkspace.tests.factories import (
    UserFactory,
    SourceTableFactory,
    MasterDataSetFactory,
)


class TestDeleteUnusedDatasetsUsers:
    @pytest.mark.django_db(transaction=True)
    def test_deletes_expired_and_unused_users(self):
        ensure_databases_configured().handle()

        user = UserFactory(email='test@foo.bar')
        st = SourceTableFactory(
            dataset=MasterDataSetFactory.create(
                user_access_type='REQUIRES_AUTHENTICATION'
            )
        )

        source_tables = source_tables_for_user(user)
        db_role_schema_suffix = db_role_schema_suffix_for_user(user)
        user_creds_to_drop = new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            postgres_user(user.email),
            user,
            valid_for=datetime.timedelta(days=31),
        )
        qs_creds_to_drop = new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            postgres_user(user.email, suffix='qs'),
            user,
            valid_for=datetime.timedelta(seconds=0),
        )
        qs_creds_to_keep = new_private_database_credentials(
            db_role_schema_suffix,
            source_tables,
            postgres_user(user.email, suffix='qs'),
            user,
            valid_for=datetime.timedelta(minutes=1),
        )

        connections[st.database.memorable_name].cursor().execute('COMMIT')

        # Make sure that `qs_creds_to_drop` has definitely expired
        time.sleep(1)

        with mock.patch('dataworkspace.apps.applications.utils.gevent.sleep'):
            delete_unused_datasets_users()

        with connections[st.database.memorable_name].cursor() as cursor:
            cursor.execute(
                "SELECT usename FROM pg_catalog.pg_user WHERE usename IN %s",
                [
                    (
                        user_creds_to_drop[0]['db_user'],
                        qs_creds_to_drop[0]['db_user'],
                        qs_creds_to_keep[0]['db_user'],
                    )
                ],
            )
            assert cursor.fetchall() == [(qs_creds_to_keep[0]['db_user'],)]
