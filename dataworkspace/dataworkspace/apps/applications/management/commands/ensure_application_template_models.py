import json


from django.db import IntegrityError
from django.conf import settings
from django.core.management.base import BaseCommand

from dataworkspace.apps.applications.models import ApplicationTemplate


class Command(BaseCommand):
    '''The application template models are populated by environment variables,
    They can do with being in the database so ApplicationInstance models have
    some sort of foreign key, and tests don't have to worry about fixtures or
    editing the database.

    This also is a small stepping stone to allowing application templates to
    be dynamically created.

    We leverage the database-enforced uniqueness on the name of a template,
    so this is command is safe to be performed concurrently by multiple
    instances
    '''

    help = (
        'Ensures the database has the application template models from the environment'
    )

    def handle(self, *args, **options):
        self.stdout.write('ensure_application_template_models started')

        desired_application_templates = settings.APPLICATION_TEMPLATES
        self.stdout.write(
            'Ensuring ApplicationTemplate {}'.format(settings.APPLICATION_TEMPLATES)
        )

        for desired_application_template in desired_application_templates:
            self.stdout.write(
                'Checking {}'.format(desired_application_template['NICE_NAME'])
            )
            try:
                ApplicationTemplate.objects.create(
                    visible=False,
                    host_basename=desired_application_template['HOST_BASENAME'],
                    nice_name=desired_application_template['NICE_NAME'],
                    spawner=desired_application_template['SPAWNER'],
                    spawner_time=int(desired_application_template['SPAWNER_TIME']),
                    spawner_options=json.dumps(
                        desired_application_template.get('SPAWNER_OPTIONS', '{}')
                    ),
                )
            except IntegrityError:
                template = ApplicationTemplate.objects.get(
                    host_basename=desired_application_template['HOST_BASENAME']
                )
                template.nice_name = desired_application_template['NICE_NAME']
                template.spawner = desired_application_template['SPAWNER']
                template.spawner_time = int(
                    desired_application_template['SPAWNER_TIME']
                )
                template.spawner_options = json.dumps(
                    desired_application_template.get('SPAWNER_OPTIONS', '{}')
                )
                template.save()
                self.stdout.write(
                    'Updated {}'.format(desired_application_template['NICE_NAME'])
                )
            else:
                self.stdout.write(
                    'Created {}'.format(desired_application_template['NICE_NAME'])
                )

        self.stdout.write(
            self.style.SUCCESS('ensure_application_template_models finished')
        )
