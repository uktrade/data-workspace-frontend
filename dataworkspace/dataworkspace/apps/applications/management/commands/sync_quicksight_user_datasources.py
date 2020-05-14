import hashlib
from typing import List, Dict

import boto3
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.conf import settings

from dataworkspace.apps.core.utils import (
    source_tables_for_user,
    new_private_database_credentials,
    persistent_postgres_user,
)


QS_DATASOURCE_PERMS = [
    'quicksight:DescribeDataSource',
    'quicksight:DescribeDataSourcePermissions',
    'quicksight:PassDataSource',
]


class Command(BaseCommand):
    '''Sync master datasets and user permissions from Data Workspace to AWS QuickSight.
    '''

    help = 'Sync master datasets and user permissions from Data Workspace to AWS QuickSight.'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ENVIRONMENT = settings.ENVIRONMENT.lower()

    def _stable_identification_suffix(self, arn):
        return hashlib.sha256(arn.encode('utf-8')).hexdigest()[:8]

    def _create_datasources_for_user(
        self, data_client, account_id, quicksight_user, creds
    ):
        for cred in creds:
            db_name = cred['memorable_name']
            data_source_id = (
                "data-workspace-"
                + self.ENVIRONMENT
                + "-"
                + self._stable_identification_suffix(quicksight_user['Arn'])
            )
            data_source_name = f"Data Workspace - {db_name}"
            if self.ENVIRONMENT != "production":
                data_source_name = f"{self.ENVIRONMENT.upper()} - {data_source_name}"

            data_source_params = dict(
                AwsAccountId=account_id,
                DataSourceId=data_source_id,
                Name=data_source_name,
                Type='AURORA_POSTGRESQL',
                DataSourceParameters={
                    "AuroraPostgreSqlParameters": {
                        "Host": cred['db_host'],
                        "Port": int(cred['db_port']),
                        "Database": cred['db_name'],
                    }
                },
                Credentials={
                    "CredentialPair": {
                        "Username": cred['db_user'],
                        "Password": cred['db_password'],
                    }
                },
                Permissions=[
                    {
                        'Principal': quicksight_user['Arn'],
                        'Actions': QS_DATASOURCE_PERMS,
                    }
                ],
                VpcConnectionProperties={
                    "VpcConnectionArn": settings.QUICKSIGHT_VPC_ARN
                },
            )

            self.stdout.write(f"-> Creating data source: {data_source_id}")

            try:
                data_client.create_data_source(**data_source_params)
                self.stdout.write(f"-> Created: {data_source_id}")
            except data_client.exceptions.ResourceExistsException:
                self.stdout.write(
                    f"-> Data source already exists: {data_source_id}. Updating ..."
                )
                data_client.update_data_source(**data_source_params)
                self.stdout.write(f"-> Updated data source: {data_source_id}")

    def handle(self, *args, **options):
        self.stdout.write('sync_quicksight_user_datasources started')

        # QuickSight manages users in a single specific region
        user_client = boto3.client(
            'quicksight', region_name=settings.QUICKSIGHT_USER_REGION
        )
        # Data sources can be in other regions - so here we use the Data Workspace default from its env vars.
        data_client = boto3.client('quicksight')

        account_id = boto3.client('sts').get_caller_identity().get('Account')

        quicksight_user_list: List[Dict[str, str]] = user_client.list_users(
            AwsAccountId=account_id, Namespace='default'
        )['UserList']

        for quicksight_user in quicksight_user_list:
            user_arn = quicksight_user['Arn']
            user_email = quicksight_user['Email']
            dw_user = get_user_model().objects.filter(email=user_email).first()
            if not dw_user:
                self.stdout.write(
                    f"Skipping {user_email} - cannot match with Data Workspace user."
                )
                continue
            else:
                # We technically ignore the case for where a single email has multiple matches on DW, but I'm not
                # sure this is a case that can happen - and if it can, we don't care while prototyping.
                self.stdout.write(f"Creating QuickSight resources for {dw_user}")

            source_tables = source_tables_for_user(dw_user)
            db_role_schema_suffix = self._stable_identification_suffix(user_arn)

            # This creates a DB user for each of our datasets DBs. These users are intended to be long-lived,
            # so they might already exist. If this is the case, we still generate a new password, as at the moment
            # these user accounts only last for 31 days by default - so we need to update the password to keep them
            # from expiring.
            creds = new_private_database_credentials(
                db_role_schema_suffix,
                source_tables,
                persistent_postgres_user(user_email, suffix='quicksight'),
                allow_existing_user=True,
            )

            self._create_datasources_for_user(
                data_client, account_id, quicksight_user, creds
            )

        self.stdout.write(
            self.style.SUCCESS('sync_quicksight_user_datasources finished')
        )


if __name__ == '__main__':
    settings.configure()
    Command().handle()
