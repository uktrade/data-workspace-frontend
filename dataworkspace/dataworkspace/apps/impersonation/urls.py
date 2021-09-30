from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.impersonation.views import impersonate

urlpatterns = [
    path('<int:id>', login_required(impersonate), name='index',),
    # path(
    #     '<uuid:dataset_uuid>',
    #     login_required(DatasetAccessRequest.as_view()),
    #     name='dataset',
    # ),
]
