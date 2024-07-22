from django.views.generic import DetailView
from dataworkspace.apps.datasets.views import EditBaseView
from django.urls import reverse
from dataworkspace.apps.datasets.utils import find_dataset, get_dataset_table
from django.shortcuts import get_object_or_404


class AddTableView(DetailView):
    template_name = "datasets/add_table/about_this_service.html"

    def get_object(self, queryset=None):
        return find_dataset(self.kwargs["pk"], self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object
        ctx["backlink"] = reverse("datasets:dataset_detail", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})

        return ctx


class TableSchemaView(EditBaseView, DetailView):
    template_name = "datasets/add_table/table_schema.html"

    def get_object(self, queryset=None):
        return find_dataset(self.kwargs["pk"], self.request.user)

    def _get_source(self):
        return get_object_or_404(self.obj.sourcetable_set.all())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object
        ctx["backlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        ctx["schema"] = self._get_source().schema
        ctx["nextlink"] = reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})

        return ctx
