from rest_framework import serializers

from dataworkspace.apps.datasets.models import DataSet


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSet
        fields = (
            "id",
            "data_catalogue_editors",
        )
