import hashlib

import boto3

from django.conf import (
    settings,
)
from django.contrib.auth import (
    get_user_model,
)
from django.core.management.base import (
    BaseCommand,
)

from app.shared import (
    new_private_database_credentials,
)


class Command(BaseCommand):
    help = 'Creates and saves DB credentials for all SSO users'

    def handle(self, *args, **options):
        self.stdout.write('store_db_creds_in_s3 started')

        bucket = settings.NOTEBOOKS_BUCKET
        self.stdout.write('Will store credentials in bucket {}'.format(bucket))

        s3_client = boto3.client('s3')

        User = get_user_model()
        all_users = User.objects.order_by('last_name', 'first_name', 'id')
        for user in all_users:
            self.stdout.write(f'Creating credentials for {user.email}')
            creds = new_private_database_credentials(user.email)
            # Create a profile in case it doesn't have one
            user.save()
            s3_prefix = 'user/federated/' + hashlib.sha256(str(user.profile.sso_id).encode('utf-8')).hexdigest() + '/'
            for cred in creds:
                key = f'{s3_prefix}.db_credentials_{cred["memorable_name"]}'
                self.stdout.write(f'Putting credentials in {key}')
                s3_client.put_object(
                    Body=str(creds).encode('utf-8'), 
                    Bucket=bucket,
                    Key=key,
                )
            self.stdout.write(str(creds))

        self.stdout.write(self.style.SUCCESS('store_db_creds_in_s3 finished'))
