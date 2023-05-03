import json


import psycopg2
from django.conf import settings
from django.contrib.postgres.aggregates.general import ArrayAgg
from django.db import models
from django.db.models import F, Q, Value, Case, When
from django.db.models.functions import Substr
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.postgres.fields import ArrayField
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination

from dataworkspace.apps.api_v1.mixins import TimestampSinceFilterMixin
from dataworkspace.apps.api_v1.pagination import TimestampCursorPagination
from dataworkspace.apps.core.utils import (
    database_dsn,
    StreamingHttpResponseWithoutDjangoDbConnection,
)
from dataworkspace.apps.datasets.constants import (
    DataSetType,
    TagType,
    SecurityClassificationAndHandlingInstructionType,
)
from dataworkspace.apps.datasets.models import (
    SourceTable,
    DataSet,
    ReferenceDataset,
    ToolQueryAuditLog,
    VisualisationCatalogueItem,
    ReferenceDatasetField,
)
from dataworkspace.apps.api_v1.datasets.serializers import (
    CatalogueItemSerializer,
    ToolQueryAuditLogSerializer,
)


def _get_dataset_columns(connection, source_table):
    sql = psycopg2.sql.SQL("SELECT * from {}.{} LIMIT 0").format(
        psycopg2.sql.Identifier(source_table.schema),
        psycopg2.sql.Identifier(source_table.table),
    )
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return [c[0] for c in cursor.description]


def _get_dataset_rows(connection, sql, query_args=None, cursor_itersize=1000):
    query_args = [] if query_args is None else query_args
    with connection.cursor(name="api_v1.datasets.views.get-rows") as cursor:
        cursor.itersize = cursor_itersize
        cursor.arraysize = cursor_itersize
        cursor.execute(sql, query_args)

        while True:
            rows = cursor.fetchmany(cursor_itersize)
            for row in rows:
                yield row
            if not rows:
                break


def _get_dataset_primary_key(connection, schema, table):
    check_is_table = psycopg2.sql.SQL(
        """
        SELECT
            CASE
                WHEN pg_class.relkind = 'r' THEN 'table'::text
                WHEN pg_class.relkind = 'v' THEN 'view'::text
                ELSE pg_class.relkind::text
            END
        FROM pg_class
                 INNER JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
        WHERE pg_namespace.nspname = %s
          AND pg_class.relname = %s;
        """
    )
    sql = psycopg2.sql.SQL(
        """
        SELECT
            pg_attribute.attname AS column_name
        FROM
            pg_catalog.pg_class pg_class_table
        INNER JOIN
            pg_catalog.pg_index ON pg_index.indrelid = pg_class_table.oid
        INNER JOIN
            pg_catalog.pg_class pg_class_index ON pg_class_index.oid = pg_index.indexrelid
        INNER JOIN
            pg_catalog.pg_namespace ON pg_namespace.oid = pg_class_table.relnamespace
        INNER JOIN
            pg_catalog.pg_attribute ON pg_attribute.attrelid = pg_class_index.oid
        WHERE
            pg_namespace.nspname = %s
            AND pg_class_table.relname = %s
            AND pg_index.indisprimary
        ORDER BY
            pg_attribute.attnum
        """
    )

    with connection.cursor() as cursor:
        cursor.execute(check_is_table, (schema, table))
        result = cursor.fetchall()

        if len(result) == 0:
            raise ValueError(f"Table does not exist: `{schema}`.`{table}`")
        if result[0][0] != "table":
            raise ValueError(
                f"Cannot get primary keys from something other than an ordinary table. "
                f"`{schema}`.`{table}` is a: {result[0][0]}"
            )

        cursor.execute(sql, (schema, table))
        return [row[0] for row in cursor.fetchall()]


def _len_chunk_header(num_chunk_bytes):
    return len("%X\r\n" % num_chunk_bytes)


def _get_streaming_http_response(streaming_class, request, primary_key, columns, rows):
    # StreamingHttpResponse translates to HTTP/1.1 chunking performed by gunicorn. However,
    # we don't have any visibility on the actual bytes sent as part of the HTTP body, i.e. each
    # chunk header and footer. We also don't appear to be able to work-around it and implement
    # our own chunked-encoder that makes these things visible. The best thing we can do is make
    # a good guess as to what these are, and add their lengths to the total number of bytes sent

    def yield_chunks(row_bytes):
        nonlocal queue
        nonlocal num_bytes_queued
        nonlocal num_bytes_sent
        nonlocal num_bytes_sent_and_queued

        queue.append(row_bytes)
        num_bytes_queued += len(row_bytes)
        num_bytes_sent_and_queued += len(row_bytes)
        while num_bytes_queued >= chunk_size:
            to_send_bytes = b"".join(queue)
            chunk, to_send_bytes = (
                to_send_bytes[:chunk_size],
                to_send_bytes[chunk_size:],
            )
            queue = [to_send_bytes] if to_send_bytes else []
            num_bytes_queued = len(to_send_bytes)
            num_bytes_sent += len(chunk) + _len_chunk_header(len(chunk)) + len_chunk_footer
            yield chunk

    def yield_data(columns, rows, base_url):
        yield from yield_chunks(b'{"headers": ')
        yield from yield_chunks(json.dumps(columns).encode("utf-8"))
        yield from yield_chunks(b', "values": [')
        for i, row in enumerate(rows):
            row_bytes = json.dumps(row, default=str).encode("utf-8")
            if i > 0:
                row_bytes = b"," + row_bytes
            yield from yield_chunks(row_bytes)

            if num_bytes_sent_and_queued > num_bytes_max:
                search_after = [columns.index(k) for k in primary_key]
                search_after = [row[i] for i in search_after]
                search_after = "&".join(["$searchAfter={}".format(k) for k in search_after])
                next_url = "{}?{}".format(base_url, search_after)
                yield from yield_chunks(b'], "next": "' + next_url.encode("utf-8") + b'"}')
                break
        else:
            yield from yield_chunks(b'], "next": null}')
        yield from yield_remaining()

    def yield_remaining():
        if queue:
            yield b"".join(queue)

    num_bytes_max = 49_990_000
    len_chunk_footer = len("\r\n")
    chunk_size = 16384
    queue = []
    num_bytes_queued = 0
    num_bytes_sent = 0
    num_bytes_sent_and_queued = 0

    base_url = request.build_absolute_uri().split("?")[0]
    return streaming_class(
        yield_data(columns, rows, base_url), content_type="application/json", status=200
    )


def dataset_api_view_GET(request, dataset_id, source_table_id):
    source_table = get_object_or_404(
        SourceTable, id=source_table_id, dataset__id=dataset_id, dataset__deleted=False
    )

    search_after = request.GET.getlist("$searchAfter")

    with psycopg2.connect(
        database_dsn(settings.DATABASES_DATA[source_table.database.memorable_name])
    ) as connection:
        primary_key = _get_dataset_primary_key(connection, source_table.schema, source_table.table)

        if not primary_key:
            raise ValueError(
                f"Cannot order response without a primary key on the table: "
                f"`{source_table.schema}`.`{source_table.table}`"
            )

        if search_after == []:
            sql = psycopg2.sql.SQL(
                """
                    select
                        *
                    from {}.{}
                    order by {}
                """
            ).format(
                psycopg2.sql.Identifier(source_table.schema),
                psycopg2.sql.Identifier(source_table.table),
                psycopg2.sql.SQL(",").join(map(psycopg2.sql.Identifier, primary_key)),
            )
        else:
            sql = psycopg2.sql.SQL(
                """
                    select
                        *
                    from {}.{}
                    where ({}) > ({})
                    order by {}
                """
            ).format(
                psycopg2.sql.Identifier(source_table.schema),
                psycopg2.sql.Identifier(source_table.table),
                psycopg2.sql.SQL(",").join(map(psycopg2.sql.Identifier, primary_key)),
                psycopg2.sql.SQL(",").join(psycopg2.sql.Placeholder() * len(search_after)),
                psycopg2.sql.SQL(",").join(map(psycopg2.sql.Identifier, primary_key)),
            )

        columns = _get_dataset_columns(connection, source_table)
        rows = _get_dataset_rows(connection, sql, query_args=search_after)

    return _get_streaming_http_response(
        StreamingHttpResponseWithoutDjangoDbConnection,
        request,
        primary_key,
        columns,
        rows,
    )


def reference_dataset_api_view_GET(request, group_slug, reference_slug):
    ref_dataset = get_object_or_404(
        ReferenceDataset.objects.live(),
        published=True,
        group__slug=group_slug,
        slug=reference_slug,
    )
    primary_key = ref_dataset._meta.pk
    search_after = (request.GET.getlist("$searchAfter") or [0])[
        0
    ]  # only one primary key is used for reference datasets

    def get_rows(field_names):
        query_set = (
            ref_dataset.get_record_model_class()
            .objects.filter(reference_dataset=ref_dataset)
            .filter(**{f"{primary_key.name}__gt": search_after})
            .order_by(primary_key.name)
        )
        for record in query_set:
            values = [None] * len(field_names)
            for field in ref_dataset.fields.all():
                if field.data_type == ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                    relationship = getattr(record, field.relationship_name)
                    values[field_names.index(field.name)] = (
                        getattr(
                            relationship,
                            field.linked_reference_dataset_field.column_name,
                        )
                        if relationship
                        else None
                    )
                else:
                    values[field_names.index(field.name)] = getattr(record, field.column_name)
            yield values

    field_names = ref_dataset.export_field_names
    field_names.sort()
    rows = get_rows(field_names)
    return _get_streaming_http_response(
        StreamingHttpResponse, request, primary_key.name, field_names, rows
    )


def _replace(items, a, b):
    return [b if i == a else i for i in items]


def _static_char(val, **kwargs):
    return models.Value(val, models.CharField(**kwargs))


def _static_int(val, **kwargs):
    return models.Value(val, models.IntegerField(**kwargs))


def _static_bool(val, **kwargs):
    return models.Value(val, models.BooleanField(null=True, **kwargs))


class CatalogueItemsInstanceViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list catalogue items for consumption by data flow.
    """

    fields = [
        "id",
        "name",
        "short_description",
        "description",
        "published",
        "created_date",
        "published_at",
        "information_asset_owner",
        "information_asset_manager",
        "enquiries_contact",
        "licence",
        "slug",
        "purpose",
        "source_tags",
        "draft",
        "dictionary",
        "personal_data",
        "retention_policy",
        "eligibility_criteria",
        "licence_url",
        "restrictions_on_usage",
        "user_access_type",
        "authorized_email_domains",
        "user_ids",
        "security_classification_display",
        "sensitivity_name",
        "quicksight_id",
    ]
    queryset = (
        DataSet.objects.live()
        .annotate(purpose=models.F("type"))
        .annotate(
            source_tags=ArrayAgg(
                "tags__name",
                filter=models.Q(tags__type=TagType.SOURCE),
                distinct=True,
            )
        )
        .annotate(
            user_ids=ArrayAgg(
                "datasetuserpermission__user",
                filter=Q(datasetuserpermission__user__isnull=False),
                distinct=True,
            )
        )
        .annotate(draft=_static_bool(None))
        .annotate(dictionary=F("dictionary_published"))
        .annotate(
            security_classification_display=Case(
                *[
                    When(government_security_classification=c[0], then=Value(c[1]))
                    for c in SecurityClassificationAndHandlingInstructionType.choices
                ],
                output_field=models.CharField(),
            )
        )
        .annotate(sensitivity_name=ArrayAgg("sensitivity__name", distinct=True))
        .annotate(quicksight_id=Value([], output_field=ArrayField(models.TextField())))
        .exclude(type=DataSetType.REFERENCE)
        .values(*fields)
        .union(
            ReferenceDataset.objects.live()
            .annotate(personal_data=_static_char(None))
            .annotate(retention_policy=_static_char(None))
            .annotate(eligibility_criteria=_static_char(None))
            .annotate(user_access_type=_static_int(None))
            .annotate(authorized_email_domains=_static_int(None))
            .annotate(purpose=_static_int(DataSetType.REFERENCE))
            .annotate(
                source_tags=ArrayAgg(
                    "tags__name",
                    filter=models.Q(tags__type=TagType.SOURCE),
                    distinct=True,
                )
            )
            .annotate(user_ids=Value([], output_field=ArrayField(models.IntegerField())))
            .annotate(draft=F("is_draft"))
            .annotate(dictionary=F("published"))
            .annotate(
                security_classification_display=Case(
                    *[
                        When(government_security_classification=c[0], then=Value(c[1]))
                        for c in SecurityClassificationAndHandlingInstructionType.choices
                    ],
                    output_field=models.CharField(),
                )
            )
            .annotate(sensitivity_name=ArrayAgg("sensitivity__name", distinct=True))
            .annotate(quicksight_id=Value([], output_field=ArrayField(models.TextField())))
            .values(*_replace(fields, "id", "uuid"))
        )
        .union(
            VisualisationCatalogueItem.objects.live()
            .annotate(purpose=_static_int(DataSetType.VISUALISATION))
            .annotate(
                source_tags=ArrayAgg(
                    "tags__name",
                    filter=models.Q(tags__type=TagType.SOURCE),
                    distinct=True,
                )
            )
            .annotate(
                user_ids=ArrayAgg(
                    "visualisationuserpermission__user",
                    filter=Q(visualisationuserpermission__user__isnull=False),
                    distinct=True,
                )
            )
            .annotate(draft=_static_bool(None))
            .annotate(dictionary=_static_bool(None))
            .annotate(
                security_classification_display=Case(
                    *[
                        When(government_security_classification=c[0], then=Value(c[1]))
                        for c in SecurityClassificationAndHandlingInstructionType.choices
                    ],
                    output_field=models.CharField(),
                )
            )
            .annotate(sensitivity_name=ArrayAgg("sensitivity__name", distinct=True))
            .annotate(
                quicksight_id=ArrayAgg(
                    "visualisationlink__identifier",
                    filter=Q(visualisationlink__visualisation_type="QUICKSIGHT"),
                    default=None,
                    distinct=True,
                )
            )
            .values(
                *fields,
            )
        )
    ).order_by("created_date")

    serializer_class = CatalogueItemSerializer
    # PageNumberPagination is used instead of CursorPagination
    # as filters cannot be applied to a union-ed queryset.
    pagination_class = PageNumberPagination


class ToolQueryAuditLogViewSet(TimestampSinceFilterMixin, viewsets.ModelViewSet):
    """
    API endpoint to list tool query audit logs for ingestion by data flow
    """

    # Due to there being a few queries in the logs with > 1 million chars
    # we truncate the query at the db level before it gets to the serializer
    queryset = (
        ToolQueryAuditLog.objects.defer("query_sql")
        .annotate(
            truncated_query_sql=Substr(
                "query_sql", 1, settings.TOOL_QUERY_LOG_API_QUERY_TRUNC_LENGTH
            )
        )
        .prefetch_related("tables")
    )
    serializer_class = ToolQueryAuditLogSerializer
    pagination_class = TimestampCursorPagination
