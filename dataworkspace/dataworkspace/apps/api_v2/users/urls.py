from django.urls import path
from dataworkspace.apps.api_v2.users import PendingAuthorizedUsersViewSet

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r"summary_pending_users", PendingAuthorizedUsersViewSet)
urlpatterns = router.urls
