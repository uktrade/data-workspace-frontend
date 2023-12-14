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

    EventLogFactory.create(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Superset"}
    )

    EventLogFactory.create(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Quicksight"}
    )

    EventLogFactory.create(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Data Explorer"}
    )

    EventLogFactory.create(
        event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Someones tool"}
    )

    EventLogFactory.create(
        user=user, event_type=EventLog.TYPE_USER_TOOL_LINK_STARTED, extra={"tool": "Data Explorer"}
    )

    EventLogFactory.create(
        user=user,
        extra={"tool": "ECS Tool"},
        event_type=EventLog.TYPE_USER_TOOL_ECS_STARTED,
        related_object=ApplicationInstanceFactory.create(),
    )

    response = client.get(reverse("api-v2:recent_tools:eventlog-list"))
    recent_tools = response.json()["results"]
    assert len(recent_tools) == 4
    assert recent_tools[0]["extra"]["tool"] == "ECS Tool"
    assert recent_tools[1]["extra"]["tool"] == "Data Explorer"
    assert recent_tools[2]["extra"]["tool"] == "Quicksight"
    assert recent_tools[3]["extra"]["tool"] == "Superset"
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
