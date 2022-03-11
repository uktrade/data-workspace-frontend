import json

import pytest
from django.conf import settings
from django.db import connections
from django.urls import reverse
from waffle.testutils import override_flag

from dataworkspace.apps.explorer import models
from dataworkspace.apps.explorer.constants import CHART_BUILDER_SCHEMA
from dataworkspace.tests.explorer import factories
from dataworkspace.tests.factories import DataSetChartBuilderChartFactory


def create_temporary_results_table(query_log):
    with connections["my_database"].cursor() as cursor:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {CHART_BUILDER_SCHEMA}")
        cursor.execute(f"DROP TABLE IF EXISTS {CHART_BUILDER_SCHEMA}._tmp_query_{query_log.id}")
        cursor.execute(
            f"CREATE TABLE {CHART_BUILDER_SCHEMA}._tmp_query_{query_log.id} "
            "(id int primary key, data text)"
        )
        cursor.execute(
            f"INSERT INTO {CHART_BUILDER_SCHEMA}._tmp_query_{query_log.id} VALUES (1, 2)"
        )


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_creation_from_query_log_not_owner(client, staff_user):
    query_log = factories.QueryLogFactory.create(run_by_user=staff_user)
    response = client.get(reverse("explorer:explorer-charts:create-chart", args=(query_log.id,)))
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_creation_from_query_log(staff_client, staff_user):
    query_log = factories.QueryLogFactory(run_by_user=staff_user)
    num_query_logs = models.QueryLog.objects.count()
    num_charts = models.ChartBuilderChart.objects.count()
    response = staff_client.get(
        reverse("explorer:explorer-charts:create-chart", args=(query_log.id,))
    )
    assert models.QueryLog.objects.count() == num_query_logs + 1
    assert models.ChartBuilderChart.objects.count() == num_charts + 1
    assert response.status_code == 302


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_edit_not_owner(staff_client):
    chart = factories.ChartBuilderChartFactory.create()
    response = staff_client.get(reverse("explorer:explorer-charts:edit-chart", args=(chart.id,)))
    assert response.status_code == 404
    response = staff_client.post(
        reverse("explorer:explorer-charts:edit-chart", args=(chart.id,)),
        json.dumps({"config": {"updated": "config"}}),
        content_type="application/json",
    )
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_edit(staff_client, staff_user):
    query_log = factories.QueryLogFactory(run_by_user=staff_user)
    chart = factories.ChartBuilderChartFactory.create(
        created_by=staff_user, query_log=query_log, chart_config={"some": "config"}
    )
    response = staff_client.post(
        reverse("explorer:explorer-charts:edit-chart", args=(chart.id,)),
        json.dumps({"config": {"updated": "config"}}),
        content_type="application/json",
    )
    assert response.status_code == 200
    chart.refresh_from_db()
    assert chart.chart_config == {"updated": "config"}


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_query_status_not_owner(staff_client, user):
    chart = factories.ChartBuilderChartFactory.create(
        created_by=user,
        query_log=factories.QueryLogFactory(run_by_user=user),
        chart_config={"some": "config"},
    )
    response = staff_client.get(
        reverse("explorer:explorer-charts:chart-query-status", args=(chart.id,))
    )
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_query_status(staff_client, staff_user):
    chart = factories.ChartBuilderChartFactory.create(
        created_by=staff_user,
        query_log=factories.QueryLogFactory(run_by_user=staff_user),
        chart_config={"some": "config"},
    )
    response = staff_client.get(
        reverse("explorer:explorer-charts:chart-query-status", args=(chart.id,))
    )
    assert response.status_code == 200
    assert response.json() == {"columns": [], "error": None, "state": 0}


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_query_results_not_owner(staff_client, user):
    chart = factories.ChartBuilderChartFactory.create(
        created_by=user,
        query_log=factories.QueryLogFactory(run_by_user=user),
        chart_config={"some": "config"},
    )
    response = staff_client.get(
        reverse("explorer:explorer-charts:chart-query-results", args=(chart.id,))
    )
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_query_results(staff_client, staff_user):
    chart = factories.ChartBuilderChartFactory.create(
        created_by=staff_user,
        query_log=factories.QueryLogFactory(run_by_user=staff_user, rows=10),
        chart_config={"some": "config"},
    )
    create_temporary_results_table(chart.query_log)
    response = staff_client.get(
        reverse("explorer:explorer-charts:chart-query-results", args=(chart.id,))
    )
    assert response.status_code == 200
    assert response.json() == {
        "data": {"data": ["2"], "id": [1]},
        "duration": 1000.0,
        "total_rows": 10,
    }


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_delete_not_owner(staff_client, user):
    query_log = factories.QueryLogFactory(run_by_user=user)
    chart = factories.ChartBuilderChartFactory.create(created_by=user, query_log=query_log)
    response = staff_client.post(
        reverse("explorer:explorer-charts:delete-chart", args=(chart.id,))
    )
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_delete_view(staff_client, staff_user):
    query_log = factories.QueryLogFactory(run_by_user=staff_user)
    chart = factories.ChartBuilderChartFactory.create(created_by=staff_user, query_log=query_log)
    num_charts = models.ChartBuilderChart.objects.count()
    response = staff_client.post(
        reverse("explorer:explorer-charts:delete-chart", args=(chart.id,))
    )
    assert response.status_code == 302
    assert models.ChartBuilderChart.objects.count() == num_charts - 1


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_delete_published_chart(staff_client, staff_user):
    query_log = factories.QueryLogFactory(run_by_user=staff_user)
    chart = factories.ChartBuilderChartFactory.create(created_by=staff_user, query_log=query_log)
    DataSetChartBuilderChartFactory.create(chart=chart)
    num_charts = models.ChartBuilderChart.objects.count()
    response = staff_client.post(
        reverse("explorer:explorer-charts:delete-chart", args=(chart.id,))
    )
    assert response.status_code == 302
    assert models.ChartBuilderChart.objects.count() == num_charts


@pytest.mark.django_db(transaction=True)
@override_flag(settings.CHART_BUILDER_BUILD_CHARTS_FLAG, active=True)
def test_chart_list_view(staff_user, staff_client, user):
    factories.ChartBuilderChartFactory.create(
        created_by=staff_user, query_log=factories.QueryLogFactory(run_by_user=staff_user)
    )
    factories.ChartBuilderChartFactory.create(
        created_by=user, query_log=factories.QueryLogFactory(run_by_user=user)
    )
    response = staff_client.get(reverse("explorer:explorer-charts:list-charts"))
    assert response.status_code == 200
    assert response.context_data["charts"].count() == 1
