from django.urls import path

from dataworkspace.apps.accounts.utils import login_required
from dataworkspace.apps.case_studies.views import CaseStudyDetailView, CaseStudyListView

urlpatterns = [
    path('', login_required(CaseStudyListView.as_view()), name='case-studies'),
    path('<str:slug>', login_required(CaseStudyDetailView.as_view()), name='case-study'),
]
