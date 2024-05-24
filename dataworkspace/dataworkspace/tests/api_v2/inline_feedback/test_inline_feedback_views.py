import pytest
from django.urls import reverse
from rest_framework import status

from dataworkspace.tests import factories


@pytest.mark.django_db
def test_unauthenticated_inline_feedback(unauthenticated_client):
    response = unauthenticated_client.get(reverse("api-v2:inline_feedback:create"))
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_creating_inline_feedback(client, user):
    client.force_login(user)
    response = client.post(
        reverse("api-v2:inline_feedback:create"),
        {"location": "some location", "was_this_page_helpful": "true"},
        follow=True,
    )
    assert response.json() == {
        "id": 1,
        "location": "some location",
        "was_this_page_helpful": True,
        "inline_feedback_choices": None,
        "more_detail": None,
    }
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_updating_inline_feedback(client, user):
    client.force_login(user)
    feedback = factories.InlineFeedbackFactory.create()
    response = client.patch(
        reverse("api-v2:inline_feedback:update", args=f"{feedback.id}"),
        data={"inline_feedback_choices": "awesome", "more_detail": "blah blah"},
        content_type="application/json",
    )
    assert response.json() == {
        "id": feedback.id,
        "location": feedback.location,
        "was_this_page_helpful": True,
        "inline_feedback_choices": "awesome",
        "more_detail": "blah blah",
    }
    assert response.status_code == status.HTTP_200_OK
