from collections import defaultdict
from typing import List, Dict

import boto3
import psycopg2
from django.core.management.base import BaseCommand
from django.conf import settings

from dataworkspace.apps.core.utils import database_dsn
from dataworkspace.apps.datasets.models import MasterDataset


QUICKSIGHT_COLUMN_TYPES_MAP = defaultdict(
    lambda: 'STRING',
    **{
        "date": 'DATETIME',
        "smallint": 'INTEGER',
        "bigint": "INTEGER",
        "integer": "INTEGER",
        "boolean": 'BOOLEAN',
        "numeric": 'DECIMAL',
        "real": "DECIMAL",
        "double precision": "DECIMAL",
        "timestamp with time zone": "TIMESTAMP",
        "json": "JSON",
        "jsonb": "JSON",
    },
)

QS_DATASOURCE_ALL_PERMS = [
    'quicksight:UpdateDataSourcePermissions',
    'quicksight:DescribeDataSource',
    'quicksight:DescribeDataSourcePermissions',
    'quicksight:PassDataSource',
    'quicksight:UpdateDataSource',
    'quicksight:DeleteDataSource',
]

QS_DATASET_ALL_PERMS = [
    'quicksight:UpdateDataSetPermissions',
    'quicksight:DescribeDataSet',
    'quicksight:DescribeDataSetPermissions',
    'quicksight:PassDataSet',
    'quicksight:DescribeIngestion',
    'quicksight:ListIngestions',
    'quicksight:UpdateDataSet',
    'quicksight:DeleteDataSet',
    'quicksight:CreateIngestion',
    'quicksight:CancelIngestion',
]

QS_DATASET_USER_PERMS = [
    'quicksight:DescribeDataSet',
    'quicksight:DescribeDataSetPermissions',
    'quicksight:PassDataSet',
    'quicksight:DescribeIngestion',
    'quicksight:ListIngestions',
]


class Command(BaseCommand):
    '''Sync master datasets and user permissions from Data Workspace to AWS QuickSight.
    '''

    help = 'Sync master datasets and user permissions from Data Workspace to AWS QuickSight.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _make_sourcetable_id(self, sourcetable):
        return f"{settings.ENVIRONMENT.upper()}-{str(sourcetable.id)}"

    def _get_dataset_columns(self, connection, sourcetable):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s and table_name = %s",
                [sourcetable.schema, sourcetable.table],
            )
            return cursor.fetchall()

    def _format_input_columns(self, db_config, sourcetable):
        with psycopg2.connect(database_dsn(db_config)) as connection:
            columns = self._get_dataset_columns(connection, sourcetable)

        return [
            {"Name": column_name, "Type": QUICKSIGHT_COLUMN_TYPES_MAP[data_type]}
            for column_name, data_type in columns
        ]

    def _dataset_users_with_access(
        self, dataset: MasterDataset, quicksight_user_list: List[Dict[str, str]]
    ) -> set:
        if dataset.user_access_type == 'REQUIRES_AUTHENTICATION':
            return {user['Arn'] for user in quicksight_user_list}

        quicksight_user_emails = [user['Email'] for user in quicksight_user_list]
        authorized_users = set(
            user['user__email']
            for user in dataset.datasetuserpermission_set.filter(
                user__email__in=quicksight_user_emails
            ).values("user__email")
        )

        # The QS datasource owner should always have access to every dataset.
        principals_needing_access = {settings.QUICKSIGHT_DATASOURCE_USER_ARN}

        principals_needing_access.update(
            {
                user['Arn']
                for user in quicksight_user_list
                if user['Email'] in authorized_users
            }
        )

        return principals_needing_access

    def _grant_permissions_to_sourcetable(
        self, data_client, account_id, sourcetable, principals
    ):
        grant_arns = [
            {
                "Principal": principal,
                "Actions": QS_DATASET_ALL_PERMS
                if principal == settings.QUICKSIGHT_DATASOURCE_USER_ARN
                else QS_DATASET_USER_PERMS,
            }
            for principal in principals
        ]

        if grant_arns:
            data_client.update_data_set_permissions(
                AwsAccountId=account_id,
                DataSetId=self._make_sourcetable_id(sourcetable),
                GrantPermissions=grant_arns,
            )

    def _revoke_permissions_to_sourcetable(
        self, data_client, account_id, sourcetable, principals
    ):
        revoke_arns = [
            {"Principal": principal, "Actions": QS_DATASET_ALL_PERMS}
            for principal in principals
        ]

        if revoke_arns:
            data_client.update_data_set_permissions(
                AwsAccountId=account_id,
                DataSetId=self._make_sourcetable_id(sourcetable),
                RevokePermissions=revoke_arns,
            )

    def _sync_permissions_to_dataset(
        self, data_client, account_id, qs_users, dataset, sourcetable
    ):
        data_set_permissions = data_client.describe_data_set_permissions(
            AwsAccountId=account_id, DataSetId=self._make_sourcetable_id(sourcetable)
        )['Permissions']
        self.stdout.write(
            f"-> Current principals with access: {[u['Principal'] for u in data_set_permissions]}"
        )

        all_principals_needing_access = self._dataset_users_with_access(
            dataset, qs_users
        )
        self.stdout.write(
            f"-> Principals that should have access: {all_principals_needing_access}"
        )
        principals_to_grant_access = all_principals_needing_access.difference(
            set(user['Principal'] for user in data_set_permissions)
        )
        self.stdout.write(f"-> Adding principals: {principals_to_grant_access}")
        self._grant_permissions_to_sourcetable(
            data_client, account_id, sourcetable, principals_to_grant_access
        )

        principals_to_revoke_access = set(
            user['Principal'] for user in data_set_permissions
        ).difference(all_principals_needing_access)
        self.stdout.write(f"-> Removing principals: {principals_to_revoke_access}")
        self._revoke_permissions_to_sourcetable(
            data_client, account_id, sourcetable, principals_to_revoke_access
        )

        final_data_source_principals = set(
            user['Principal']
            for user in data_client.describe_data_set_permissions(
                AwsAccountId=account_id,
                DataSetId=self._make_sourcetable_id(sourcetable),
            )['Permissions']
        )

        if all_principals_needing_access.symmetric_difference(
            final_data_source_principals
        ):
            self.stderr.write(
                "-> Error syncing permissions for sourcetable.\n"
                f"  Incorrectly DO have access: {final_data_source_principals - all_principals_needing_access}\n"
                f"  Incorrectly DO NOT have access: {all_principals_needing_access - final_data_source_principals}"
            )

    def _create_dataset(
        self, data_client, account_id, db_config, datasource, dataset, sourcetable
    ):
        self.stdout.write(f"-> Creating quicksight dataset for: {sourcetable}")

        physical_table = {
            self._make_sourcetable_id(sourcetable): {
                "RelationalTable": {
                    "DataSourceArn": datasource['DataSource']['Arn'],
                    "InputColumns": self._format_input_columns(db_config, sourcetable),
                    "Name": sourcetable.table,
                    "Schema": sourcetable.schema,
                }
            }
        }
        logical_table = {
            self._make_sourcetable_id(sourcetable): {
                "Alias": sourcetable.name,
                "Source": {"PhysicalTableId": self._make_sourcetable_id(sourcetable)},
            }
        }

        self.stdout.write(f"--> Physical table: {str(physical_table)}")
        self.stdout.write(f"--> Logical table: {str(logical_table)}")

        try:
            sourcetable_name = f"{sourcetable.schema}.{sourcetable.table}"
            if settings.ENVIRONMENT != "Production":
                sourcetable_name = (
                    f"{settings.ENVIRONMENT.upper()} - {sourcetable_name}"
                )

            qs_dataset = data_client.create_data_set(
                AwsAccountId=account_id,
                DataSetId=self._make_sourcetable_id(sourcetable),
                Name=sourcetable_name,
                ImportMode='DIRECT_QUERY',
                PhysicalTableMap=physical_table,
                LogicalTableMap=logical_table,
                Permissions=[
                    {
                        "Principal": settings.QUICKSIGHT_DATASOURCE_USER_ARN,
                        "Actions": QS_DATASET_ALL_PERMS,
                    }
                ],
            )
            self.stdout.write(str(qs_dataset))
        except data_client.exceptions.ResourceExistsException as e:
            self.stdout.write(f'--> {e}')

        self.stdout.write("-> Done.")

    def _create_datasource(self, data_client, account_id, db_name, db_config):
        data_source_id = f'data-workspace-{settings.ENVIRONMENT}'

        try:
            self.stdout.write(f"-> Creating data source: {data_source_id}")
            qs_datasource = data_client.create_data_source(
                AwsAccountId=account_id,
                DataSourceId=data_source_id,
                Name=f"Data Workspace - {settings.ENVIRONMENT} - {db_name}",
                Type='AURORA_POSTGRESQL',
                DataSourceParameters={
                    "AuroraPostgreSqlParameters": {
                        "Host": db_config['HOST'],
                        "Port": int(db_config['PORT']),
                        "Database": db_config['NAME'],
                    }
                },
                Credentials={
                    "CredentialPair": {
                        "Username": db_config['USER'],
                        "Password": db_config['PASSWORD'],
                    }
                },
                Permissions=[
                    {
                        'Principal': settings.QUICKSIGHT_DATASOURCE_USER_ARN,
                        'Actions': QS_DATASOURCE_ALL_PERMS,
                    }
                ],
                VpcConnectionProperties={
                    "VpcConnectionArn": settings.QUICKSIGHT_VPC_ARN
                },
            )
            self.stdout.write(str(qs_datasource))
        except data_client.exceptions.ResourceExistsException as e:
            self.stdout.write(f'--> {e}')

        return data_client.describe_data_source(
            AwsAccountId=account_id, DataSourceId=data_source_id
        )

    def handle(self, *args, **options):
        self.stdout.write('sync_sources_and_permissions_to_quicksight started')

        # QuickSight manages users in a single specific region
        user_client = boto3.client(
            'quicksight', region_name=settings.QUICKSIGHT_USER_REGION
        )
        # Data sources can be in other regions - so here we use the Data Workspace default from its env vars.
        data_client = boto3.client('quicksight')

        account_id = boto3.client('sts').get_caller_identity().get('Account')

        db = list(settings.DATABASES_DATA.keys())[0]
        db_config = settings.DATABASES_DATA[db]

        quicksight_user_list: List[Dict[str, str]] = user_client.list_users(
            AwsAccountId=account_id, Namespace='default'
        )['UserList']

        datasource = self._create_datasource(data_client, account_id, db, db_config)

        for dataset in MasterDataset.objects.live().filter(published=True):
            for source_table in dataset.sourcetable_set.all():
                try:
                    self._create_dataset(
                        data_client,
                        account_id,
                        db_config,
                        datasource,
                        dataset,
                        source_table,
                    )
                    self._sync_permissions_to_dataset(
                        data_client,
                        account_id,
                        quicksight_user_list,
                        dataset,
                        source_table,
                    )
                except data_client.exceptions.ClientError as e:
                    self.stdout.write(f'--> {e}')

        self.stdout.write(
            self.style.SUCCESS('sync_sources_and_permissions_to_quicksight finished')
        )


if __name__ == '__main__':
    settings.configure()
    Command().handle()
