from rest_framework.routers import DefaultRouter

from dataworkspace.apps.api_v2.recent_tools.views import RecentToolsViewSet

router = DefaultRouter()
router.register(r"recent_tools", RecentToolsViewSet)
urlpatterns = router.urls
