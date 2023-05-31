import uuid

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from freezegun import freeze_time
from rest_framework import status
from rest_framework.fields import DateTimeField

from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests.api_v1.base import BaseAPIViewTest
from dataworkspace.tests import factories
from dataworkspace.tests.factories import EventLogFactory, VisualisationLinkFactory


@pytest.mark.django_db
class TestEventLogAPIView(BaseAPIViewTest):
    url = reverse("api-v1:eventlog:events")
    factory = factories.DatasetLinkDownloadEventFactory
    pagination_class = "dataworkspace.apps.api_v1.pagination.TimestampCursorPagination.page_size"

    def expected_response(self, eventlog):
        return {
            "event_type": eventlog.get_event_type_display(),
            "id": eventlog.id,
            "related_object": {
                "id": str(eventlog.related_object.id)
                if isinstance(eventlog.related_object.id, uuid.UUID)
                else eventlog.related_object.id,
                "name": eventlog.related_object.get_full_name()
                if isinstance(eventlog.related_object, get_user_model())
                else eventlog.related_object.name,
                "type": "User"
                if isinstance(eventlog.related_object, get_user_model())
                else eventlog.related_object.get_type_display(),
            },
            "timestamp": DateTimeField().to_representation(eventlog.timestamp),
            "user_id": eventlog.user.id,
            "extra": eventlog.extra,
        }

    @pytest.mark.parametrize(
        "event_log_factory",
        (
            factories.DatasetLinkDownloadEventFactory,
            factories.DatasetQueryDownloadEventFactory,
            factories.ReferenceDatasetDownloadEventFactory,
            factories.DatasetAccessRequestEventFactory,
            factories.DatasetAccessGrantedEventFactory,
            factories.DatasetAccessRevokedEventFactory,
        ),
    )
    def test_success(self, unauthenticated_client, event_log_factory):
        eventlog1 = event_log_factory()
        eventlog2 = event_log_factory()
        response = unauthenticated_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == sorted(
            [self.expected_response(eventlog1), self.expected_response(eventlog2)],
            key=lambda x: x["id"],
        )

    def test_visualisation_approval_success(self, unauthenticated_client):
        # We create the visualisation approvals, which in turn create the event log items
        approval_0 = factories.VisualisationApprovalFactory()
        approval_1 = factories.VisualisationApprovalFactory()

        response = unauthenticated_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"][0]["event_type"] == "Visualisation approved"
        assert response.json()["results"][0]["related_object"]["id"] == str(approval_0.id)
        assert response.json()["results"][1]["event_type"] == "Visualisation approved"
        assert response.json()["results"][1]["related_object"]["id"] == str(approval_1.id)

    def test_visualisation_view(self, unauthenticated_client):
        vis_link = VisualisationLinkFactory.create(
            visualisation_type="QUICKSIGHT",
            visualisation_catalogue_item__name="my quicksight vis",
        )
        EventLogFactory.create(
            event_type=EventLog.TYPE_VIEW_QUICKSIGHT_VISUALISATION,
            related_object=vis_link,
        )

        response = unauthenticated_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"][0]["event_type"] == "View AWS QuickSight visualisation"
        assert response.json()["results"][0]["related_object"]["id"] == str(vis_link.id)
        assert response.json()["results"][0]["related_object"]["name"] == str(vis_link.name)
        assert response.json()["results"][0]["related_object"]["type"] == "QUICKSIGHT"

    @pytest.mark.parametrize(
        "event_log_factory",
        (
            factories.DatasetLinkDownloadEventFactory,
            factories.DatasetQueryDownloadEventFactory,
            factories.ReferenceDatasetDownloadEventFactory,
            factories.DatasetAccessRequestEventFactory,
            factories.DatasetAccessGrantedEventFactory,
            factories.DatasetAccessRevokedEventFactory,
        ),
    )
    def test_timestamp_filter(self, unauthenticated_client, event_log_factory):
        with freeze_time("2020-01-01 00:01:00"):
            event_log_factory()
        with freeze_time("2020-01-01 00:01:01"):
            eventlog2 = event_log_factory()
        with freeze_time("2020-01-01 00:02:00"):
            eventlog3 = event_log_factory()
        with freeze_time("2020-01-01 00:03:00"):
            event_log_factory()
        response = unauthenticated_client.get(
            self.url + "?from=2020-01-01 00:01:01&to=2020-01-01 00:03:00"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"] == sorted(
            [self.expected_response(eventlog2), self.expected_response(eventlog3)],
            key=lambda x: x["id"],
        )
