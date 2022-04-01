import psycopg2
from django.conf import settings

from dataworkspace.apps.core.charts.models import ChartBuilderChart
from dataworkspace.apps.core.utils import (
    close_all_connections_if_not_in_atomic_block,
    database_dsn,
)
from dataworkspace.apps.explorer.models import QueryLog
from dataworkspace.apps.explorer.tasks import _run_query
from dataworkspace.cel import celery_app
from dataworkspace.settings.base import DATABASES_DATA


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def run_chart_builder_query(chart_id):
    chart = ChartBuilderChart.objects.get(id=chart_id)
    query_log = chart.query_log
    with psycopg2.connect(database_dsn(DATABASES_DATA[query_log.connection])) as conn:
        _run_query(
            conn,
            query_log,
            query_log.page,
            query_log.page_size,
            settings.EXPLORER_QUERY_TIMEOUT_MS,
            chart.get_temp_table_name(),
        )


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def refresh_chart_thumbnail(chart_id):
    ChartBuilderChart.objects.get(id=chart_id).refresh_thumbnail()


@celery_app.task()
@close_all_connections_if_not_in_atomic_block
def refresh_published_chart_data():
    for chart in ChartBuilderChart.objects.filter(datasets__isnull=False):
        original_query_log = chart.query_log
        original_table_name = chart.get_temp_table_name()
        chart.query_log = QueryLog.objects.create(
            sql=original_query_log.sql,
            query_id=original_query_log.query_id,
            run_by_user=chart.created_by,
            connection=original_query_log.connection,
            page=1,
            page_size=None,
        )
        chart.save()
        run_chart_builder_query(chart.id)
        chart.refresh_thumbnail()
        with psycopg2.connect(database_dsn(DATABASES_DATA[original_query_log.connection])) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {original_table_name}")
