import csv
import os

from django.core.management import BaseCommand
from django.db import DataError

from app import models


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--dataset',
            type=int,
            help='The id of the data set to import records to',
            required=True
        )
        parser.add_argument(
            '--csv',
            type=str,
            help='The path to the csv file to import',
            required=True
        )

    def handle(self, *args, **kwargs):
        # Ensure the file exists
        if not os.path.exists(kwargs['csv']):
            raise ValueError('Provided csv path does not exist')

        # Ensure the reference dataset exists
        try:
            dataset = models.ReferenceDataset.objects.get(pk=kwargs['dataset'], deleted=False)
        except models.ReferenceDataset.DoesNotExist:
            raise ValueError('Data set with id {} does not exist'.format(kwargs['dataset']))

        fields = dataset.fields.all()
        update_count = 0
        create_count = 0

        with open(kwargs['csv'], 'r') as fh:
            reader = csv.DictReader(fh)

            # Check that all fields are provided
            column_names = [x.lower() for x in reader.fieldnames]
            for field in fields:
                if field.name.lower() not in column_names:
                    raise ValueError('Column {} does not exist in csv'.format(field.name.lower()))

            for row in reader:
                existing = dataset.get_record_by_custom_id(row[dataset.identifier_field.name])
                record_id = existing['dw_int_id'] if existing is not None else None
                data = {}
                for k, v in row.items():
                    if v == '':
                        v = None
                    data[k] = v

                try:
                    dataset.save_record(record_id, data)
                except DataError as e:
                    raise ValueError(
                        'Invalid data provided at row with identifier {}'.format(
                            row[dataset.identifier_field.name]
                        ), e
                    )

                if record_id is None:
                    create_count += 1
                else:
                    update_count += 1

        print('Created {} and updated {} reference data sets'.format(
            create_count,
            update_count
        ))
