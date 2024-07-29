from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, FormView
from django.http import HttpResponseRedirect

from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.datasets.views import EditBaseView
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.add_table.forms import TableSchemaForm


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


class TableSchemaView(EditBaseView, DetailView, FormView):
    template_name = "datasets/add_table/table_schema.html"
    form_class = TableSchemaForm

    def get_object(self, queryset=None):
        return find_dataset(self.kwargs["pk"], self.request.user)

    def _get_schemas(self):
        schemas = []
        if self.object.type == DataSetType.MASTER:
            for table in self.obj.sourcetable_set.all():
                schemas += [table.schema]
        elif self.object.type == DataSetType.REFERENCE:
            schemas = ["public"]
        else:
            # Invalid dataset, return error or redirect?
            return ""

        # This should return a list with no duplicates, need to test
        return list(set(schemas))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object
        ctx["schemas"] = self._get_schemas()
        print("schemas", ctx["schemas"])
        ctx["is_multiple_schemas"] = len(ctx["schemas"]) > 1
        print("Multiple", ctx["is_multiple_schemas"])
        ctx["backlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})

        return ctx
    
    def form_valid(self, form):
        cleaned = form.cleaned_data
        print('cleaned', cleaned)
        print('form.schema', form.schema[0].__dict__)
        if form.schema:
            return HttpResponseRedirect(reverse("datasets:add_table:add-table", args={self.kwargs["pk"]}))
    
