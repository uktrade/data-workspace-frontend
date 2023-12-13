import pytest
from django.urls import reverse
from rest_framework import status

from dataworkspace.tests.factories import EventLogFactory, ApplicationInstanceFactory
from dataworkspace.apps.eventlog.models import EventLog


@pytest.mark.django_db
def test_unauthenticated_recent_tools(unauthenticated_client):
    response = unauthenticated_client.get(reverse("api-v2:recent_tools:eventlog-list"))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_ordering_and_filtering_recent_tools(client, user):
    client.force_login(user)

    user_event1 = EventLogFactory(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Superset"}
    )

    user_event2 = EventLogFactory(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Quicksight"}
    )

    user_event3 = EventLogFactory(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Data Explorer"}
    )

    user_event4 = EventLogFactory(
        user=user,
        event_type=EventLog.TYPE_USER_TOOL_ECS_STARTED,
        related_object=ApplicationInstanceFactory.create(),
    )

    EventLogFactory(
        event_type=EventLog.TYPE_USER_TOOL_ECS_STARTED,
        related_object=ApplicationInstanceFactory.create(),
    )

    response = client.get(reverse("api-v2:recent_tools:eventlog-list"))
    recent_tools = response.json()
    assert len(recent_tools["results"]) == 4
    assert recent_tools["results"][0]["id"] == user_event4.id
    assert recent_tools["results"][1]["id"] == user_event3.id
    assert recent_tools["results"][2]["id"] == user_event2.id
    assert recent_tools["results"][3]["id"] == user_event1.id
    assert response.status_code == status.HTTP_200_OK


def test_tool_urls(client, user):
    client.force_login(user)
    EventLogFactory.create(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Superset"}
    )
    EventLogFactory.create(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Quicksight"}
    )
    EventLogFactory.create(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Data Explorer"}
    )

    ApplicationInstanceFactory.create(owner=user)

    EventLogFactory.create(
        user=user,
        event_type=EventLog.TYPE_USER_TOOL_ECS_STARTED,
        related_object=None,
    )

    response = client.get(reverse("api-v2:recent_tools:eventlog-list"))
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["results"][4]["tool_url"] == "/tools/superset/redirect"
    assert response.json()["results"][3]["tool_url"] == "/tools/quicksight/redirect"
    assert response.json()["results"][2]["tool_url"] == "/tools/explorer/redirect"
    assert response.json()["results"][1]["tool_url"] is not None
    assert response.json()["results"][0]["tool_url"] is None
