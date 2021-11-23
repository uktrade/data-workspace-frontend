import itertools
import os
import re


def normalise_environment(key_values):
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

# pgweb only allows one database
_, dsn = list(env['DATABASE_DSN'].items())[0]
user = re.search(r'user=([a-z0-9_]+)', dsn).groups()[0]
password = re.search(r'password=([a-zA-Z0-9_]+)', dsn).groups()[0]
port = re.search(r'port=(\d+)', dsn).groups()[0]
dbname = re.search(r'dbname=([a-z0-9_\-]+)', dsn).groups()[0]
host = re.search(r'host=([a-z0-9_\-\.]+)', dsn).groups()[0]

print(f'postgres://{user}:{password}@{host}:{port}/{dbname}')
