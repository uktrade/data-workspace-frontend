from django.db import connection
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from psycopg2 import sql

from app import models


@receiver(post_save, sender=models.ReferenceDataset)
def reference_dataset_post_save(sender, instance, created, **kwargs):
    """
    On ReferenceDataset save create the associated table
    :param sender:
    :param instance:
    :param created:
    :param kwargs:
    :return:
    """
    if created:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    '''
                    CREATE TABLE {table_name} (
                        dw_int_id SERIAL NOT NULL CONSTRAINT {constraint} PRIMARY KEY,
                        reference_dataset_id INTEGER NOT NULL,
                        updated_date timestamp not null default CURRENT_TIMESTAMP
                    )
                    '''
                ).format(
                    table_name=sql.Identifier(instance.table_name),
                    constraint=sql.Identifier(instance.table_name + '_pkey'),
                )
            )


@receiver(post_save, sender=models.ReferenceDatasetField)
def reference_dataset_field_post_save(sender, instance, created, **kwargs):
    """
    On ReferenceDatasetField save update the associated table.
    :param sender:
    :param instance:
    :param created:
    :param kwargs:
    :return:
    """
    if created:
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL(
                    '''
                    ALTER TABLE {table_name}
                    ADD COLUMN {column_name} {data_type} {nullable}
                    '''
                ).format(
                    table_name=sql.Identifier(instance.reference_dataset.table_name),
                    column_name=sql.Identifier(instance.name),
                    data_type=sql.SQL(instance.get_postgres_datatype()),
                    nullable=sql.SQL('not null' if instance.required else 'null')
                )
            )
    else:
        original = instance._original_values
        with connection.cursor() as cursor:
            if original['name'] != instance.name:
                cursor.execute(
                    sql.SQL(
                        '''
                        ALTER TABLE {table_name}
                        RENAME COLUMN {orig_column_name} TO {new_column_name}
                        '''
                    ).format(
                        table_name=sql.Identifier(instance.reference_dataset.table_name),
                        orig_column_name=sql.Identifier(original['name']),
                        new_column_name=sql.Identifier(instance.name),
                    )
                )
            if original['data_type'] != instance.data_type:
                cursor.execute(
                    sql.SQL(
                        '''
                        ALTER TABLE {table_name}
                        ALTER COLUMN {column_name} TYPE {data_type}
                        USING {column_name}::text::{data_type}
                        '''
                    ).format(
                        table_name=sql.Identifier(instance.reference_dataset.table_name),
                        column_name=sql.Identifier(instance.name),
                        data_type=sql.SQL(instance.get_postgres_datatype()),
                    )
                )


@receiver(post_delete, sender=models.ReferenceDatasetField)
def reference_dataset_field_post_delete(sender, instance, **kwargs):
    """
    On ReferenceDataField delete drop the column
    :param sender:
    :param instance:
    :param kwargs:
    :return:
    """
    with connection.cursor() as cursor:
        cursor.execute(
            sql.SQL(
                '''
                ALTER TABLE {table_name}
                DROP COLUMN {column_name}
                '''
            ).format(
                table_name=sql.Identifier(instance.reference_dataset.table_name),
                column_name=sql.Identifier(instance._original_values['name']),
            )
        )
