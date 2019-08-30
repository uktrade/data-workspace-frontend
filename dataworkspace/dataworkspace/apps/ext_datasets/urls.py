from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.ext_datasets.views import (
    OMISClientSurveyReportView,
    OMISCancelledOrderReportView,
    OMISCompletedOrderReportView
)

urlpatterns = [
    path('omis-dataset/client-survey-report/',
         login_required(OMISClientSurveyReportView.as_view()),
         name='omis-client-survey-report'),
    path('omis-dataset/cancelled-order-report/',
         login_required(OMISCancelledOrderReportView.as_view()),
         name='omis-cancelled-order-report'),
    path('omis-dataset/completed-order-report/',
         login_required(OMISCompletedOrderReportView.as_view()),
         name='omis-completed-order-report'),
]
