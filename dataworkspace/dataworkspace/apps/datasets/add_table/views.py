from django.views.generic import TemplateView
from django.urls import reverse


class AddTableView(TemplateView):
    template_name = "datasets/add_table/about_this_service.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["backlink"] = reverse("datasets:dataset_detail", args={kwargs["pk"]})
        return context
