from django.urls import reverse
from django.views.generic import DetailView, FormView, TemplateView
from django.http import HttpResponseRedirect

from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.datasets.constants import DataSetType
from dataworkspace.apps.datasets.add_table.forms import TableSchemaForm, DescriptiveNameForm


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
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        schemas = self.get_schemas(dataset)
        schema_choices = list(((x, x) for x in schemas))
        initial.update(
            {
                "schema_choices": schema_choices,
            }
        )
        return initial

    def get_schemas(self, dataset):
        schemas = []
        if dataset.type == DataSetType.MASTER:
            tables = list(dataset.sourcetable_set.all())
            for table in tables:
                schemas.append(table.schema)

        return list(set(schemas))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        schemas = self.get_schemas(dataset)
        ctx["model"] = dataset
        ctx["schema"] = schemas[0]
        ctx["is_multiple_schemas"] = len(schemas) > 1
        ctx["backlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        return ctx

    def form_valid(self, form):
        clean_data = form.cleaned_data
        schema = clean_data["schema"]
        return HttpResponseRedirect(
            reverse("datasets:add_table:classification-check", args=(self.kwargs["pk"], schema))
        )


class ClassificationCheckView(TemplateView):
    template_name = "datasets/add_table/classification_check.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["model"] = dataset
        ctx["classification"] = (
            dataset.get_government_security_classification_display() or "Unclassified"
        ).title()
        ctx["backlink"] = reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse(
            "datasets:add_table:descriptive-name", args=(self.kwargs["pk"], self.kwargs["schema"])
        )
        return ctx


class DescriptiveNameView(FormView):
    template_name = "datasets/add_table/descriptive_name.html"
    form_class = DescriptiveNameForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["model"] = dataset
        ctx["backlink"] = reverse(
            "datasets:add_table:classification-check",
            args=(self.kwargs["pk"], self.kwargs["schema"]),
        )
        # TODO add next link
        ctx["nextlink"] = ""
        return ctx

    def form_valid(self, form):
        clean_data = form.cleaned_data
        descriptive_name = clean_data["descriptive_name"]
        # TODO add next link
        return HttpResponseRedirect("/")
