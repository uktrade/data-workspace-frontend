from rest_framework.routers import DefaultRouter
from dataworkspace.apps.api_v2.your_profile.views import ProfileViewSet


router = DefaultRouter()
router.register(r"your_profile", ProfileViewSet)
urlpatterns = router.urls
