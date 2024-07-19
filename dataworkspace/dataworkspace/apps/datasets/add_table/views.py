from django.views.generic import DetailView
from django.urls import reverse
from dataworkspace.apps.datasets.utils import find_dataset
import inspect



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
    
class TableSchemaView(DetailView):
    template_name = "datasets/add_table/table_schema.html"

    def get_schema(self, queryset=None):
        return find_dataset(self.kwargs["pk"], self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["model"] = self.object
        ctx["backlink"] = reverse("datasets:add_table:add-table", args={self.kwargs["pk"]})
        print('HERE', inspect.getmembers(self.object))

        return ctx
