from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.impersonation.views import impersonate, stop_impersonating

urlpatterns = [
    path('start/<int:user_id>', login_required(impersonate), name='start',),
    path('stop', login_required(stop_impersonating), name='stop',),
]
