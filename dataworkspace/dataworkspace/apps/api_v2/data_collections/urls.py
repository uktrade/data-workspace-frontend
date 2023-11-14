from rest_framework.routers import DefaultRouter

from dataworkspace.apps.api_v2.data_collections.views import (
    DataCollectionViewSet,
)

router = DefaultRouter()
router.register(r"collections", DataCollectionViewSet)
urlpatterns = router.urls
