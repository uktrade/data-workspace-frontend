import pytest
from django.contrib.contenttypes.models import ContentType

from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.tests.factories import (
    VisualisationTemplateFactory,
    VisualisationApprovalFactory,
)


class TestVisualisationApproval:
    @pytest.mark.django_db
    def test_eventlog_entry_on_initial_approve(self):
        v = VisualisationTemplateFactory.create()

        a = VisualisationApprovalFactory.create(approved=True, visualisation=v)

        events = EventLog.objects.filter(
            event_type=EventLog.TYPE_VISUALISATION_APPROVED,
            object_id=a.id,
            content_type=ContentType.objects.get_for_model(a),
        )
        assert len(events) == 1, "A visualisation approval eventlog entry should be created"

    @pytest.mark.django_db
    def test_eventlog_entry_on_unapprove(self):
        v = VisualisationTemplateFactory.create()
        a = VisualisationApprovalFactory.create(approved=True, visualisation=v)

        a.approved = False
        a.save()

        events = EventLog.objects.filter(
            event_type=EventLog.TYPE_VISUALISATION_UNAPPROVED,
            object_id=a.id,
            content_type=ContentType.objects.get_for_model(a),
        )
        assert len(events) == 1, "A visualisation unapproval eventlog entry should be created"

    @pytest.mark.django_db
    def test_unapproved_record_cannot_be_reapproved(self):
        v = VisualisationTemplateFactory.create()
        a = VisualisationApprovalFactory.create(approved=True, visualisation=v)
        a.approved = False
        a.save()

        a.approved = True
        with pytest.raises(ValueError) as e:
            a.save()

        assert (
            str(e.value)
            == "A new record must be created for a new approval - you cannot flip a rescinded approval."
        )
