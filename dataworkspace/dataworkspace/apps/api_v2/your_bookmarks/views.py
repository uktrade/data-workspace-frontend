from rest_framework import viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated

from dataworkspace.apps.api_v2.datasets.serializers import DatasetSerializer
from dataworkspace.apps.datasets.models import DataSet


class YourBookmarksViewSet(viewsets.ModelViewSet):
    queryset = DataSet.objects.all()
    serializer_class = DatasetSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(user_has_bookmarked=self.request.user)
