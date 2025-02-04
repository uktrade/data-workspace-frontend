from rest_framework import mixins, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from dataworkspace.apps.core.models import UserInlineFeedbackSurvey

from .serializers import FeedbackSerializer


class InlineFeedBackViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, GenericViewSet):
    queryset = UserInlineFeedbackSurvey.objects.all()
    serializer_class = FeedbackSerializer
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        location = serializer.validated_data.get("location")
        was_this_page_helpful = serializer.validated_data.get("was_this_page_helpful")
        serializer.save(was_this_page_helpful=was_this_page_helpful)
        serializer.save(location=location)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        inline_feedback_choices = serializer.validated_data.get("inline_feedback_choices")
        more_detail = serializer.validated_data.get("more_detail")
        serializer.save(inline_feedback_choices=inline_feedback_choices)
        serializer.save(more_detail=more_detail)
        return Response(serializer.data, status=status.HTTP_200_OK)
