import itertools
import json
import os
import re


# We are running behind a proxy that handles authentication
SERVER_MODE = False
MASTER_PASSWORD_REQUIRED = False

# We don't have internet access
UPGRADE_CHECK_ENABLED = False


def normalise_environment(key_values):
    '''Converts denormalised dict of (string -> string) pairs, where the first string
    is treated as a path into a nested list/dictionary structure

    {
        "FOO__1__BAR": "setting-1",
        "FOO__1__BAZ": "setting-2",
        "FOO__2__FOO": "setting-3",
        "FOO__2__BAR": "setting-4",
        "FIZZ": "setting-5",
    }

    to the nested structure that this represents

    {
        "FOO": [{
            "BAR": "setting-1",
            "BAZ": "setting-2",
        }, {
            "BAR": "setting-3",
            "BAZ": "setting-4",
        }],
        "FIZZ": "setting-5",
    }

    If all the keys for that level parse as integers, then it's treated as a list
    with the actual keys only used for sorting

    This function is recursive, but it would be extremely difficult to hit a stack
    limit, and this function would typically by called once at the start of a
    program, so efficiency isn't too much of a concern.
    '''

    # Separator is chosen to
    # - show the structure of variables fairly easily;
    # - avoid problems, since underscores are usual in environment variables
    separator = '__'

    def get_first_component(key):
        return key.split(separator)[0]

    def get_later_components(key):
        return separator.join(key.split(separator)[1:])

    without_more_components = {
        key: value for key, value in key_values.items() if not get_later_components(key)
    }

    with_more_components = {
        key: value for key, value in key_values.items() if get_later_components(key)
    }

    def grouped_by_first_component(items):
        def by_first_component(item):
            return get_first_component(item[0])

        # groupby requires the items to be sorted by the grouping key
        return itertools.groupby(sorted(items, key=by_first_component), by_first_component)

    def items_with_first_component(items, first_component):
        return {
            get_later_components(key): value
            for key, value in items
            if get_first_component(key) == first_component
        }

    nested_structured_dict = {
        **without_more_components,
        **{
            first_component: normalise_environment(
                items_with_first_component(items, first_component)
            )
            for first_component, items in grouped_by_first_component(with_more_components.items())
        },
    }

    def all_keys_are_ints():
        def is_int(string_to_test):
            try:
                int(string_to_test)
                return True
            except ValueError:
                return False

        return all([is_int(key) for key, value in nested_structured_dict.items()])

    def list_sorted_by_int_key():
        return [
            value
            for key, value in sorted(
                nested_structured_dict.items(), key=lambda key_value: int(key_value[0])
            )
        ]

    return list_sorted_by_int_key() if all_keys_are_ints() else nested_structured_dict


env = normalise_environment(os.environ)

servers = {}
passwords = []
passfile = '/pgadmin4/.pgpass'

for i, (name, dsn) in enumerate(env['DATABASE_DSN'].items()):
    user = re.search(r'user=([a-z0-9_]+)', dsn).groups()[0]
    password = re.search(r'password=([a-zA-Z0-9_]+)', dsn).groups()[0]
    port = re.search(r'port=(\d+)', dsn).groups()[0]
    dbname = re.search(r'dbname=([a-z0-9_\-]+)', dsn).groups()[0]
    host = re.search(r'host=([a-z0-9_\-\.]+)', dsn).groups()[0]

    passwords.append(f'{host}:{port}:*:{user}:{password}')
    servers[str(i)] = {
        'Name': name,
        'Group': 'Servers',
        'Port': int(port),
        'Username': user,
        'Host': host,
        'SSLMode': 'prefer',
        'MaintenanceDB': 'postgres',
        'PassFile': passfile,
    }

with open(passfile, 'w') as f:
    for password in passwords:
        f.write(password + '\n')

os.chmod(passfile, 0o600)

with open('/pgadmin4/servers.json', 'w') as f:
    f.write(json.dumps({'Servers': servers}))
