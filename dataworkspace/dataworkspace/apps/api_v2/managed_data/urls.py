from rest_framework.routers import DefaultRouter

from dataworkspace.apps.api_v2.managed_data.views import ManagedDataViewSet

router = DefaultRouter()
router.register(r"managed_data", ManagedDataViewSet)
urlpatterns = router.urls
