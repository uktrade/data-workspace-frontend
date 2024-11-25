from django.contrib.auth import get_user_model
from rest_framework import status, mixins
from rest_framework.viewsets import GenericViewSet
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from dataworkspace.apps.datasets.models import DataSet, DataSetUserPermission
from .serializers import DatasetSerializer


class EditDatasetCatalogueEditorsViewSet(
    mixins.CreateModelMixin, mixins.UpdateModelMixin, GenericViewSet
):
    queryset = DataSet.objects.all()
    serializer_class = DatasetSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_update(self, serializer):
        data_catalogue_editors = serializer.validated_data.get("data_catalogue_editors")
        serializer.save(data_catalogue_editors=data_catalogue_editors)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ResetDatasetUserPermissionsViewSet(mixins.DestroyModelMixin, GenericViewSet):
    queryset = DataSet.objects.all()
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_destroy(self, instance):
        current_authorized_users = get_user_model().objects.filter(
            datasetuserpermission__dataset=instance
        )
        for user in current_authorized_users:
            DataSetUserPermission.objects.filter(dataset=instance, user=user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
