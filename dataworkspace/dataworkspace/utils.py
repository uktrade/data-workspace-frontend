import itertools

from ecs_logging import StdlibFormatter


def normalise_environment(key_values):
    """Converts denormalised dict of (string -> string) pairs, where the first string
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
    """

    # Separator is chosen to
    # - show the structure of variables fairly easily;
    # - avoid problems, since underscores are usual in environment variables
    separator = "__"

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

        # pylint: disable=use-a-generator
        return all([is_int(key) for key, value in nested_structured_dict.items()])

    def list_sorted_by_int_key():
        return [
            value
            for key, value in sorted(
                nested_structured_dict.items(), key=lambda key_value: int(key_value[0])
            )
        ]

    return list_sorted_by_int_key() if all_keys_are_ints() else nested_structured_dict


class DataWorkspaceECSFormatter(StdlibFormatter):
    def format_to_ecs(self, record):
        result = super().format_to_ecs(record)

        # If Django has injected a `request` argument (which it does some times, e.g. when there's an exception),
        # we need to stringify it as the raw WSGIRequest cannot be serialized to JSON.
        if result.get("request"):
            result["request"] = str(result.get("request"))

        return result


TYPE_CODES_REVERSED = {
    16: "boolean",
    17: "bytea",
    18: "text",
    19: "text",
    20: "bigint",
    21: "smallint",
    22: "int2vector",
    23: "integer",
    24: "regproc",
    25: "text",
    26: "tid",
    27: "tid",
    28: "xid",
    29: "cid",
    30: "oidvector",
    32: "pg_ddl_command",
    71: "pg_type",
    75: "pg_attribute",
    81: "pg_proc",
    83: "pg_class",
    114: "json",
    142: "xml",
    194: "pg_node_tree",
    199: "json[]",
    269: "table_am_handler",
    325: "index_am_handler",
    600: "point",
    601: "lseg",
    602: "path",
    603: "box",
    604: "polygon",
    628: "line",
    650: "cidr",
    651: "cidr[]",
    700: "double precision",
    701: "double precision",
    704: "interval",
    705: "unknown",
    718: "circle",
    774: "macaddr8",
    790: "money",
    829: "macaddr",
    869: "inet",
    1000: "boolean[]",
    1001: "bytea[]",
    1002: "text[]",
    1003: "text[]",
    1005: "integer[]",
    1006: "integer[]",
    1007: "integer[]",
    1009: "text[]",
    1013: "tid[]",
    1014: "text[]",
    1015: "text[]",
    1016: "bigint[]",
    1021: "float[]",
    1022: "float[]",
    1028: "tid[]",
    1033: "aclitem",
    1040: "macaddr[]",
    1041: "inet[]",
    1042: "text",
    1043: "text",
    1082: "date",
    1083: "time",
    1114: "timestamp with time zone",
    1115: "timestamp without time zone[]",
    1182: "date[]",
    1183: "time[]",
    1184: "timestamp with time zone",
    1185: "timestamp with time zone[]",
    1186: "interval",
    1187: "interval[]",
    1231: "decimal[]",
    1266: "time",
    1270: "time[]",
    1560: "bit",
    1562: "varbit",
    1700: "numeric",
    1790: "refcursor",
    2202: "regprocedure",
    2203: "regoper",
    2204: "regoperator",
    2205: "regclass",
    2206: "regtype",
    2249: "record",
    2275: "cstring",
    2276: "any",
    2277: "anyarray",
    2278: "void",
    2279: "trigger",
    2280: "language_handler",
    2281: "internal",
    2283: "anyelement",
    2287: "_record",
    2776: "anynonarray",
    2950: "uuid",
    2951: "text[]",
    2970: "txid_snapshot",
    3115: "fdw_handler",
    3220: "pg_lsn",
    3310: "tsm_handler",
    3361: "pg_ndistinct",
    3402: "pg_dependencies",
    3500: "anyenum",
    3614: "tsvector",
    3615: "tsquery",
    3642: "gtsvector",
    3734: "regconfig",
    3769: "regdictionary",
    3802: "jsonb",
    3807: "jsonb[]",
    3831: "anyrange",
    3838: "event_trigger",
    3904: "type",
    3905: "typeARRAY",
    3906: "type",
    3907: "typeARRAY",
    3908: "tsrange",
    3909: "tsrange[]",
    3910: "tstzrange",
    3911: "tstzrange[]",
    3912: "daterange",
    3913: "daterange[]",
    3926: "int8range",
    4072: "jsonpath",
    4089: "regnamespace",
    4096: "regrole",
    4191: "regcollation",
    4451: "int4multirange",
    4532: "nummultirange",
    4533: "tsmultirange",
    4534: "tstzmultirange",
    4535: "datemultirange",
    4536: "int8multirange",
    4537: "anymultirange",
    4538: "anycompatiblemultirange",
    4600: "pg_brin_bloom_summary",
    4601: "pg_brin_minmax_multi_summary",
    5017: "pg_mcv_list",
    5038: "pg_snapshot",
    5069: "xid8",
    5077: "anycompatible",
    5078: "anycompatiblearray",
    5079: "anycompatiblenonarray",
    5080: "anycompatiblerange",
}
