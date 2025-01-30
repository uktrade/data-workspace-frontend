from django.utils.html import strip_tags
from rest_framework import serializers
from django.contrib.auth import get_user_model


from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.models import (
    DataSet,
)


class DataInsightsSerializer(serializers.ModelSerializer):

    email = serializers.SerializerMethodField()

    class Meta:
        model = DataSet
        fields = (
            "id",
            "email",
        )

    def get_email(self, obj):
        datasets = self.get_queryset()
        iam_iao_ids = datasets.values_list("information_asset_manager_id", "information_asset_owner_id")
        # emails = get_user_model().objects.filter(id__in=iam_iao_ids)
        return iam_iao_ids

    def get_queryset(self):
        return DataSet.objects.all().exclude(type=DataSetType.DATACUT)
