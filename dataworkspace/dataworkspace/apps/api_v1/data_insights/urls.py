from rest_framework.routers import DefaultRouter

from dataworkspace.apps.api_v1.data_insights.views import OwnerInsightsViewSet

router = DefaultRouter()
router.register(r"owners", OwnerInsightsViewSet)
urlpatterns = router.urls
