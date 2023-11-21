from rest_framework.routers import DefaultRouter

from dataworkspace.apps.api_v2.recent_items.views import RecentItemsViewSet

router = DefaultRouter()
router.register(r"recent_items", RecentItemsViewSet)
urlpatterns = router.urls
