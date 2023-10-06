from rest_framework.routers import DefaultRouter

from dataworkspace.apps.api_v2.datasets.views import (
    DatasetViewSet,
    ReferenceDatasetViewSet,
    VisualisationViewSet,
)

router = DefaultRouter()
router.register(r"datasets", DatasetViewSet, basename="dataset")
router.register(r"reference", ReferenceDatasetViewSet, basename="reference")
router.register(r"visualisation", VisualisationViewSet, basename="visualisation")
urlpatterns = router.urls
