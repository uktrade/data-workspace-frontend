from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.data_collections import views

urlpatterns = [
    path(
        "<int:collections_id>",
        login_required(views.CollectionsDetailView.as_view()),
        name="collections_view",
    ),
]
