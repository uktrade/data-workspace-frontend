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


class TableSchemaView(FormView):
    template_name = "datasets/add_table/table_schema.html"
    form_class = TableSchemaForm

    def get_initial(self, *args, **kwargs):
        initial = super().get_initial()
        # if self.request.method == "GET":
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        schemas = []
        if dataset.type == DataSetType.MASTER:
            tables = list(dataset.sourcetable_set.all())
            for table in tables:
                schemas.append(table.schema)
            schema_choices = list(((x, x) for x in schemas))
            initial.update(
                {
                    "schema_choices": schema_choices,
                }
            )
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["is_multiple_schemas"] = True
        ctx["backlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})  # Will change to classification check url
        return ctx

    def form_valid(self, form):
        schema = form.cleaned_data
        if schema:
            return HttpResponseRedirect(
                reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
            )
        # Need to do this with error handling as no option has been selected
        return HttpResponseRedirect(
            reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})
        )
