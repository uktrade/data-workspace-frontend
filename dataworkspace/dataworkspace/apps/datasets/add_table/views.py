from django.urls import reverse
from django.views.generic import DetailView, FormView, TemplateView
from django.http import HttpResponseRedirect, JsonResponse

from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.apps.datasets.add_table.forms import (
    TableNameForm,
    TableSchemaForm,
    DescriptiveNameForm,
)
from dataworkspace.apps.datasets.models import DataSet


class AddTableView(DetailView):
    template_name = "datasets/add_table/about_this_service.html"

    def get_object(self, queryset=None):
        return find_dataset(self.kwargs["pk"], self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object
        ctx["backlink"] = reverse("datasets:dataset_detail", args={self.kwargs["pk"]})
        ctx["nextlink"] = reverse("datasets:add_table:table-schema", args={self.kwargs["pk"]})
        ctx["preview_link"] = reverse("datasets:")
        return ctx


class ConfirmationView(TemplateView):
    template_name = "datasets/add_table/confirmation.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["backlink"] = reverse("datasets:dataset_detail", args={self.kwargs["pk"]})
        ctx["edit_link"] = reverse("datasets:edit_dataset", args={self.kwargs["pk"]})
        ctx["model_name"] = dataset.name
        source_table_id = self.get_source_table_id(dataset, kwargs["table_name"])
        ctx["preview_link"] = reverse(
            "datasets:source_table_detail",
            kwargs={"dataset_uuid": self.kwargs["pk"], "object_id": source_table_id},
        )
        return ctx

    def get_source_table_id(self, dataset: DataSet, table_name: str) -> str:
        source_tables = list(dataset.sourcetable_set.all())
        source_table_match = [st for st in source_tables if st.table == table_name]
        if len(source_table_match) < 1:
            return JsonResponse(
                {"message": f"Table name {table_name} not found in dataset."}, status=404
            )
        return source_table_match[0].id


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
        tables = list(dataset.sourcetable_set.all())
        for table in tables:
            schemas.append(table.schema)

        return list(set(schemas))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        schemas = self.get_schemas(dataset)
        ctx["model_name"] = dataset.name
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
        return ctx

    def form_valid(self, form):
        descriptive_name = form.cleaned_data["descriptive_name"]
        return HttpResponseRedirect(
            reverse(
                "datasets:add_table:table-name",
                args=(self.kwargs["pk"], self.kwargs["schema"], descriptive_name),
            )
        )


class TableNameView(FormView):
    template_name = "datasets/add_table/table_name.html"
    form_class = TableNameForm

    def get_initial(self, *args, **kwargs):
        initial = super().get_initial()
        initial.update(
            {
                "schema": self.kwargs["schema"],
                "descriptive_name": self.kwargs["descriptive_name"],
                "table_names": self.get_all_table_names(),
            }
        )
        return initial

    def is_multiple_schemas(self, dataset):
        schemas = []
        tables = list(dataset.sourcetable_set.all())
        for table in tables:
            schemas.append(table.schema)

        return len(set(schemas)) > 1

    def get_all_table_names(self):
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        table_names = []
        tables = list(dataset.sourcetable_set.all())
        for table in tables:
            table_names.append(table.name)

        return table_names

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = find_dataset(self.kwargs["pk"], self.request.user)
        ctx["is_multiple_schemas"] = self.is_multiple_schemas(dataset)
        ctx["model_name"] = dataset.name
        ctx["schema"] = self.kwargs["schema"]
        ctx["backlink"] = reverse(
            "datasets:add_table:descriptive-name",
            args=(self.kwargs["pk"], self.kwargs["schema"]),
        )
        return ctx

    def form_valid(self, form):
        # table_name = form.cleaned_data["table_name"]
        return HttpResponseRedirect(
            ("/")
            # reverse(
            #     "datasets:add_table:{NEW_PAGE}",
            #     args=(self.kwargs["pk"], self.kwargs["schema"], self.kwargs["descriptive_name"], table_name),
            # )
        )
