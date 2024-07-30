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

    # def get_form(self, form_class=None):
    #     form = self.get_form_class()(**self.get_form_kwargs())
    #     return form

    # def get_initial(self, *args, **kwargs):
    #   super().get_initial(*args, **kwargs)
    #   schema_choices = self._get_schemas()
    #   print("schemas", schema_choices)
    #   print("self", self)
    #   form = self.get_form()
    #   print("form", form)
    #   self.form.fields["schema"].choices = schema_choices

    def get_object(self, queryset=None):
        return find_dataset(self.kwargs["pk"], self.request.user)

    def _get_schemas(self):
        schemas = []
        if self.object.type == DataSetType.MASTER:
            for table in self.obj.sourcetable_set.all():
                schemas += [table.schema]
        else:
            schemas = ["public"]

        # This should return a list with no duplicates, need to test
        return list(set(schemas))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object
        ctx["schemas"] = self._get_schemas()
        ctx["is_multiple_schemas"] = len(ctx["schemas"]) > 1
        ctx["backlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})

        return ctx

    def form_valid(self, form):
        schema = ""
        for key, value in self.request.POST.lists():
            if "on" in value:
                schema = key

        # Need to pass schema value onto next pages
        if schema:
            return HttpResponseRedirect(
                reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
            )
        # Need to do this with error handling as no option has been selected
        return HttpResponseRedirect(
            reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})
        )
