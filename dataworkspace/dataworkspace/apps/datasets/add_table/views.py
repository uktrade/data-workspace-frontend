from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView

from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.datasets.views import EditBaseView


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
        ctx["schema"] = self._get_source().schema
        ctx["backlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse(
            "datasets:add_table:classification-check", args={self.kwargs["pk"]}
        )

        return ctx


class ClassificationCheckView(EditBaseView, DetailView):
    template_name = "datasets/add_table/classification_check.html"

    def get_object(self, queryset=None):
        return find_dataset(self.kwargs["pk"], self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object
        ctx["classification"] = (
            self.object.get_government_security_classification_display() or "Unclassified"
        ).title()
        ctx["backlink"] = reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse(
            "datasets:add_table:classification-check", args={self.kwargs["pk"]}
        )
        return ctx
