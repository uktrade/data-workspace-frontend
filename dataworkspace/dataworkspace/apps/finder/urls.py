from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.finder import views

urlpatterns = [
    path('', login_required(views.find_datasets), name='find_datasets'),
    path(
        "show-results/<str:schema>/<str:table>",
        login_required(views.show_results),
        name='show_results',
    ),
]
