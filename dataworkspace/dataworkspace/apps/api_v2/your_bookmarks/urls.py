from rest_framework.routers import DefaultRouter

from dataworkspace.apps.api_v2.your_bookmarks.views import YourBookmarksViewSet

router = DefaultRouter()
router.register(r"your_bookmarks", YourBookmarksViewSet)
urlpatterns = router.urls
