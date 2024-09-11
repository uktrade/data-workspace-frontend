from rest_framework import generics

from dataworkspace.apps.accounts.models import Profile
from dataworkspace.apps.accounts.serializers import ProfileSerializer


class ProfileSettingsView(generics.ListAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
