import datetime
import itertools
import logging
import re
import secrets
import string

from django.conf import (
    settings,
)
from psycopg2 import (
    connect,
    sql,
)

from app.models import (
    Privilage,
)

logger = logging.getLogger('app')


def database_dsn(database_data):
    return (
        f'host={database_data["HOST"]} port={database_data["PORT"]} ' \
        f'dbname={database_data["NAME"]} user={database_data["USER"]} ' \
        f'password={database_data["PASSWORD"]} sslmode=require'
    )


def get_private_privilages(email_address):
    logger.info('Getting privilages for: %s', email_address)
    return Privilage.objects.all().filter(
        database__is_public=False,
        user__email=email_address,
    ).order_by(
        'database__memorable_name', 'schema', 'tables', 'id'
    )


def new_private_database_credentials(user):
    password_alphabet = string.ascii_letters + string.digits
    user_alphabet = string.ascii_lowercase + string.digits

    def postgres_user():
        unique_enough = ''.join(secrets.choice(user_alphabet) for i in range(5))
        return 'user_' + re.sub('[^a-z0-9]', '_', user.email.lower()) + '_' + unique_enough

    def postgres_password():
        return ''.join(secrets.choice(password_alphabet) for i in range(64))

    def get_new_credentials(database_obj, privilages_for_database):
        user = postgres_user()
        password = postgres_password()

        database_data = settings.DATABASES_DATA[database_obj.memorable_name]
        valid_until = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
        with \
                connect(database_dsn(database_data)) as conn, \
                conn.cursor() as cur:

            cur.execute(sql.SQL('CREATE USER {} WITH PASSWORD %s VALID UNTIL %s;').format(sql.Identifier(user)), [password, valid_until])
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {};').format(sql.Identifier(database_data['NAME']), sql.Identifier(user)))

            for privilage in privilages_for_database:
                cur.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {};').format(sql.Identifier(privilage.schema), sql.Identifier(user)))
                tables_sql_list = sql.SQL(',').join([
                    sql.SQL('{}.{}').format(sql.Identifier(privilage.schema), sql.Identifier(table))
                    for table in privilage.tables.split(',')
                ])
                tables_sql = \
                    sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {};').format(sql.Identifier(privilage.schema), sql.Identifier(user)) if privilage.tables == 'ALL TABLES' else \
                    sql.SQL('GRANT SELECT ON {} TO {};').format(tables_sql_list, sql.Identifier(user))
                cur.execute(tables_sql)

        return {
            'memorable_name': database_obj.memorable_name,
            'db_name': database_data['NAME'],
            'db_host': database_data['HOST'],
            'db_port': database_data['PORT'],
            'db_user': user,
            'db_password': password,
        }

    privilages = get_private_privilages(user.email)

    return [
        get_new_credentials(database_obj, privilages_for_database)
        for database_obj, privilages_for_database in itertools.groupby(privilages, lambda privilage: privilage.database)
    ]
