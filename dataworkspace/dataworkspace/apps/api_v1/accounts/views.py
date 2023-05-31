from django.contrib.auth import get_user_model
from rest_framework import viewsets
from rest_framework.pagination import CursorPagination

from dataworkspace.apps.api_v1.accounts.serializers import UserSerializer


class UserCursorPagination(CursorPagination):
    ordering = ("id",)


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint to list EvenLog items for consumption by data flow.
    """

    queryset = get_user_model().objects.all()
    serializer_class = UserSerializer
    pagination_class = UserCursorPagination
