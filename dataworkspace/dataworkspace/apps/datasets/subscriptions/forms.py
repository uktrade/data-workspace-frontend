from dataworkspace.apps.datasets.constants import NotificationType


from dataworkspace.apps.datasets.models import DataSetSubscription
from dataworkspace.forms import (
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemRadioField,
    GOVUKDesignSystemRadiosWidget,
)


class DataSetSubscriptionForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataSetSubscription
        fields = ["notify_on_schema_change", "notify_on_data_change"]

    notification_type = GOVUKDesignSystemRadioField(
        required=True,
        label="What changes would you like to get emails about?",
        choices=NotificationType.choices,
        widget=GOVUKDesignSystemRadiosWidget,
    )
