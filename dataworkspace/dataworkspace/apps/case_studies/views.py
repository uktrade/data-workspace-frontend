from django.conf import settings
from django.views.generic import DetailView, ListView
from waffle.mixins import WaffleFlagMixin

from dataworkspace.apps.case_studies.models import CaseStudy


class CaseStudyListView(WaffleFlagMixin, ListView):
    waffle_flag = settings.CASE_STUDIES_FLAG
    queryset = CaseStudy.objects.filter(published=True)
    paginate_by = 10


class CaseStudyDetailView(WaffleFlagMixin, DetailView):
    waffle_flag = settings.CASE_STUDIES_FLAG
    queryset = CaseStudy.objects.filter(published=True)
    context_object_name = "case_study"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["other_case_studies"] = self.queryset.exclude(id=self.object.id)[:3]
        return ctx
