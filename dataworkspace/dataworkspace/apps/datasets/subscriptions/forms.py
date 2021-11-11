from dataworkspace.apps.datasets.models import DataSetSubscription
from dataworkspace.forms import (
    GOVUKDesignSystemModelForm,
    GOVUKDesignSystemBooleanField,
)


class DataSetSubscriptionForm(GOVUKDesignSystemModelForm):
    class Meta:
        model = DataSetSubscription
        fields = ['notify_on_schema_change', 'notify_on_data_change']

    notify_on_schema_change = GOVUKDesignSystemBooleanField(
        label="Each time columns are added, removed or renamed", required=False,
    )

    notify_on_data_change = GOVUKDesignSystemBooleanField(
        label="Each time data has been changed", required=False
    )
