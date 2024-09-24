from django.urls import path
from rest_framework.routers import DefaultRouter
from dataworkspace.apps.api_v2.your_profile import views


# router = DefaultRouter()
# router.register(r"your_profile", ProfileViewSet)
# urlpatterns = router.urls


urlpatterns = [
    path(
        "your_profile", views.ProfileViewSet.as_view({"get": "list"}), name="get"
    ),
    path(
        "your_profile/<int:pk>", views.ProfileViewSet.as_view({"patch": "partial_update"}), name="update"
    ),
]
