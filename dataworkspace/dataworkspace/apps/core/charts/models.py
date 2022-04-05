import copy
import io
import json
import logging
import uuid
from collections import defaultdict
from contextlib import closing
from datetime import datetime

import plotly
import psycopg2
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connections, models
from django.urls import reverse
from psycopg2 import sql

from dataworkspace.apps.core.charts.constants import CHART_BUILDER_AXIS_MAP, CHART_BUILDER_SCHEMA
from dataworkspace.apps.core.models import TimeStampedUserModel
from dataworkspace.apps.core.storage import S3FileStorage
from dataworkspace.apps.datasets.templatetags.datasets_tags import date_with_gmt_offset
from dataworkspace.apps.explorer.models import QueryLog

logger = logging.getLogger(__name__)


class ChartBuilderChartManager(models.Manager):
    def _create_chart(self, query_log, user, source=None, run_query=True):
        title = f"New chart ({date_with_gmt_offset(datetime.now())})"
        chart = self.create(
            title=title,
            created_by=user,
            query_log=query_log,
            chart_config={"layout": {"title": {"text": title}}},
            related_source=source,
        )
        if run_query:
            chart.run_query()
        return chart

    def create_from_source(self, source, user, run_query=True):
        new_query_log = QueryLog.objects.create(
            sql=source.get_chart_builder_query(),
            run_by_user=user,
            connection=source.database.memorable_name,
            page=1,
            page_size=None,
        )
        return self._create_chart(new_query_log, user, source, run_query)

    def create_from_sql(self, query, user, connection, run_query=True):
        new_query_log = QueryLog.objects.create(
            sql=query,
            run_by_user=user,
            connection=connection,
            page=1,
            page_size=None,
        )
        return self._create_chart(new_query_log, user, run_query=run_query)


class ChartBuilderChart(TimeStampedUserModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    query_log = models.ForeignKey(QueryLog, related_name="chart", on_delete=models.PROTECT)
    chart_config = models.JSONField(null=True)
    thumbnail = models.FileField(
        null=True,
        blank=True,
        storage=S3FileStorage(location="chart-builder-thumbnails"),
    )
    source_content_type = models.ForeignKey(ContentType, null=True, on_delete=models.SET_NULL)
    source_id = models.CharField(max_length=255, null=True)
    related_source = GenericForeignKey("source_content_type", "source_id")

    objects = ChartBuilderChartManager()

    class Meta:
        ordering = ("-created_date",)

    def __str__(self):
        return f"{self.title} ({self.created_by.get_full_name()})"

    def run_query(self):
        # pylint: disable=import-outside-toplevel
        from dataworkspace.apps.core.charts.tasks import run_chart_builder_query

        run_chart_builder_query.delay(self.id)

    def get_temp_table_name(self):
        return f"{CHART_BUILDER_SCHEMA}._tmp_query_{self.query_log.id}"

    def get_edit_url(self):
        return reverse("charts:edit-chart", args=(self.id,))

    def get_table_data(self, columns=None):
        table_name = self.get_temp_table_name()
        query = sql.SQL("SELECT {} from {}.{}").format(
            sql.SQL(",").join(map(sql.Identifier, columns))
            if columns is not None
            else sql.SQL("*"),
            sql.Identifier(table_name.split(".")[0]),
            sql.Identifier(table_name.split(".")[1]),
        )
        conn = connections[self.query_log.connection]
        conn.ensure_connection()
        cursor = conn.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(query)
        data = defaultdict(list)
        for row in cursor.fetchall():
            for k, v in row.items():
                data[k].append(v)
        return data

    def get_required_columns(self):
        traces = self.chart_config.get("traces", [])
        if len(traces) == 0:
            return None
        columns = []
        for trace in traces:
            for column_name in trace["meta"].get("columnNames", {}).values():
                if isinstance(column_name, dict):
                    columns += list(column_name.values())
                else:
                    columns.append(column_name)
            if trace.get("textsrc", None) is not None:
                columns.append(trace["textsrc"])
        return list(set(columns))

    def is_published(self):
        return self.datasets.count() > 0

    def refresh_thumbnail(self):
        logger.info("Refreshing thumbnail for chart %s", self.title)
        if not self.chart_config.get("traces", []):
            logger.info("No valid traces found for chart. Skipping")
            return
        config = copy.deepcopy(self.chart_config)
        config["data"] = []
        chart_data = self.get_table_data()
        for trace in config.pop("traces"):
            axis_data = CHART_BUILDER_AXIS_MAP[trace["type"]]
            if axis_data["xsrc"] not in trace and axis_data["ysrc"] not in trace:
                logger.info("Chart traces invalid. Skipping")
                continue
            for axis, src in (("x", "xsrc"), ("y", "ysrc")):
                try:
                    trace[axis_data.get(axis, axis)] = chart_data[trace[axis_data[src]]]
                except KeyError:
                    pass
            if "textsrc" in trace:
                trace["text"] = chart_data[trace["textsrc"]]
            config["data"].append(trace)

        if not config["data"]:
            logger.info("No valid traces found for chart. Skipping")
            return

        with closing(io.BytesIO()) as outfile:
            plotly.io.write_image(
                plotly.io.from_json(json.dumps(config, cls=DjangoJSONEncoder), skip_invalid=True),
                outfile,
                "png",
            )
            outfile.seek(0)
            self.thumbnail.save(
                f"chart-thumb-{self.id}.png",
                outfile,
                save=True,
            )
