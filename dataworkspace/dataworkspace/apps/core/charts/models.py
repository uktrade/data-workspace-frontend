import copy
import io
import json
import uuid
from collections import defaultdict
from contextlib import closing

import plotly
import psycopg2
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connections, models
from django.urls import reverse
from psycopg2 import sql

from dataworkspace.apps.core.charts.constants import CHART_BUILDER_AXIS_MAP, CHART_BUILDER_SCHEMA
from dataworkspace.apps.core.models import TimeStampedUserModel
from dataworkspace.apps.core.storage import S3FileStorage
from dataworkspace.apps.explorer.models import QueryLog


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

    class Meta:
        ordering = ("-created_date",)

    def __str__(self):
        return f"{self.title} ({self.created_by.get_full_name()})"

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
        if not self.chart_config.get("traces", []):
            return
        config = copy.deepcopy(self.chart_config)
        config["data"] = []
        chart_data = self.get_table_data(self.get_required_columns())
        for trace in config.pop("traces"):
            axis_data = CHART_BUILDER_AXIS_MAP[trace["type"]]
            trace[axis_data.get("x", "x")] = chart_data[trace[axis_data["xsrc"]]]
            trace[axis_data.get("y", "y")] = chart_data[trace[axis_data["ysrc"]]]
            if "textsrc" in trace:
                trace["text"] = chart_data[trace["textsrc"]]
            config["data"].append(trace)

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
