from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.data_collections import views

urlpatterns = [
    path(
        "<slug:collections_slug>",
        login_required(views.CollectionsDetailView.as_view()),
        name="collections_view",
    ),
]
