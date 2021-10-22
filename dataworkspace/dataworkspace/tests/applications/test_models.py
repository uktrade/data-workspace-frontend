import pytest

from dataworkspace.tests.factories import (
    VisualisationTemplateFactory,
    VisualisationApprovalFactory,
)


class TestVisualisationApproval:
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
