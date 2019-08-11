from django.db.backends.signals import connection_created
from django.conf import settings


def disable_constraint_checking(sender, connection, **kwargs):
    """Disable integrity constraint with sqlite for reference dataset."""
    if connection.vendor == 'sqlite':
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys = OFF;')
    connection.disable_constraint_checking()

connection_created.connect(disable_constraint_checking)
