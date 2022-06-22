from datetime import datetime, timedelta, timezone
import pytest
from freezegun import freeze_time

from dataworkspace.apps.datasets.search import (
    calculate_visualisation_average,
    calculate_dataset_average,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests import factories


@pytest.mark.django_db
def test_update_visualisation_averages(user):
    # Events over 28 days old should be ignored
    vis = factories.VisualisationCatalogueItemFactory.create(
        published_at=datetime.now() - timedelta(days=30)
    )
    with freeze_time(datetime.now() - timedelta(days=29)):
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION,
            related_object=vis,
        )
    assert calculate_visualisation_average(vis) == 0

    # Events that happened today should be ignored
    vis = factories.VisualisationCatalogueItemFactory.create(
        published_at=datetime.now() - timedelta(days=30)
    )
    factories.EventLogFactory(
        event_type=EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION,
        timestamp=datetime.now(),
        related_object=vis,
    )
    assert calculate_visualisation_average(vis) == 0

    # Events published within the last 28 days should be included
    # in the calculation
    vis = factories.VisualisationCatalogueItemFactory.create(
        published_at=datetime.now() - timedelta(days=30)
    )
    with freeze_time(datetime.now() - timedelta(days=28)):
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
        )
    with freeze_time(datetime.now() - timedelta(days=1)):
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
        )
    assert calculate_visualisation_average(vis) == 0.07142857142857142

    # A "view" event should only count once per user per day
    vis = factories.VisualisationCatalogueItemFactory.create(
        published_at=datetime.now() - timedelta(days=30)
    )
    with freeze_time(datetime.now() - timedelta(days=10)):
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
            user=user,
        )
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
            user=user,
        )
    with freeze_time(datetime.now() - timedelta(days=9)):
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
            user=user,
        )
    with freeze_time(datetime.now() - timedelta(days=8)):
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
        )
    assert calculate_visualisation_average(vis) == 0.10714285714285714

    # If vis is published less than 28 days ago calculations should start
    # from midnight the day after the day it was published
    vis = factories.VisualisationCatalogueItemFactory.create(
        published_at=datetime.now() - timedelta(days=10)
    )
    with freeze_time(datetime.now() - timedelta(days=11)):
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
        )
    with freeze_time(datetime.now() - timedelta(days=10)):
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
        )
    with freeze_time(datetime.now() - timedelta(days=9)):
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
        )
        factories.EventLogFactory(
            event_type=EventLog.TYPE_VIEW_SUPERSET_VISUALISATION,
            related_object=vis,
        )
    assert calculate_visualisation_average(vis) == 0.2222222222222222


@pytest.mark.django_db
def test_update_dataset_averages(metadata_db):
    # Events over 28 days old should be ignored
    dataset = factories.DataSetFactory.create(
        published_at=datetime.now() - timedelta(days=30), name="test_table"
    )
    table = factories.SourceTableFactory.create(
        dataset=dataset,
        database=metadata_db,
        schema="public",
        table="test_table",
    )
    user = factories.UserFactory(email="test-user@example.com")

    factories.ToolQueryAuditLogTableFactory(
        table=table.table,
        audit_log__user=user,
        audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )

    assert calculate_dataset_average(dataset) == 0

    # Events that happened today should be ignored
    factories.ToolQueryAuditLogTableFactory(
        table=table.table,
        audit_log__user=user,
        audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )

    assert calculate_dataset_average(dataset) == 0

    # Events published within the last 28 days should be included
    # in the calculation
    dataset = factories.DataSetFactory.create(
        published_at=datetime.now() - timedelta(days=30), name="test_table"
    )
    table = factories.SourceTableFactory.create(
        dataset=dataset,
        schema="public",
        table="test_table",
    )
    log_1 = factories.ToolQueryAuditLogFactory(
        user=user, timestamp=datetime.now() - timedelta(days=20)
    )
    log_2 = factories.ToolQueryAuditLogFactory(
        user=user, timestamp=datetime.now() - timedelta(days=20)
    )
    log_3 = factories.ToolQueryAuditLogFactory(
        user=user, timestamp=datetime.now() - timedelta(days=15)
    )
    factories.ToolQueryAuditLogTableFactory(
        table=table.table, schema=table.schema, audit_log=log_1
    )
    factories.ToolQueryAuditLogTableFactory(
        table=table.table, schema=table.schema, audit_log=log_2
    )

    assert calculate_dataset_average(dataset) == 0.03571428571428571

    factories.ToolQueryAuditLogTableFactory(
        table=table.table, schema=table.schema, audit_log=log_3
    )

    assert calculate_dataset_average(dataset) == 0.07142857142857142

@pytest.mark.django_db
def test_update_dataset_averages(metadata_db):
    # Events over 28 days old should be ignored
    dataset = factories.DataSetFactory.create(
        published_at=datetime.now() - timedelta(days=30), name="test_table"
    )
    table = factories.SourceTableFactory.create(
        dataset=dataset,
        database=metadata_db,
        schema="public",
        table="test_table",
    )
    user = factories.UserFactory(email="test-user@example.com")

    factories.ToolQueryAuditLogTableFactory(
        table=table.table,
        audit_log__user=user,
        audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )

    assert calculate_dataset_average(dataset) == 0

    # Events that happened today should be ignored
    factories.ToolQueryAuditLogTableFactory(
        table=table.table,
        audit_log__user=user,
        audit_log__timestamp=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )

    assert calculate_dataset_average(dataset) == 0

    # Events published within the last 28 days should be included
    # in the calculation
    dataset = factories.DataSetFactory.create(
        published_at=datetime.now() - timedelta(days=30), name="test_table"
    )
    table = factories.SourceTableFactory.create(
        dataset=dataset,
        schema="public",
        table="test_table",
    )
    log_1 = factories.ToolQueryAuditLogFactory(
        user=user, timestamp=datetime.now() - timedelta(days=20)
    )
    log_2 = factories.ToolQueryAuditLogFactory(
        user=user, timestamp=datetime.now() - timedelta(days=20)
    )
    log_3 = factories.ToolQueryAuditLogFactory(
        user=user, timestamp=datetime.now() - timedelta(days=15)
    )
    factories.ToolQueryAuditLogTableFactory(
        table=table.table, schema=table.schema, audit_log=log_1
    )
    factories.ToolQueryAuditLogTableFactory(
        table=table.table, schema=table.schema, audit_log=log_2
    )

    assert calculate_dataset_average(dataset) == 0.03571428571428571

    factories.ToolQueryAuditLogTableFactory(
        table=table.table, schema=table.schema, audit_log=log_3
    )

    assert calculate_dataset_average(dataset) == 0.07142857142857142
