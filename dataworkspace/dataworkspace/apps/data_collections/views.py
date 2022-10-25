from django.views.generic import DetailView

from dataworkspace.apps.data_collections.models import Collection


class CollectionsDetailView(DetailView):
    def get_object(self, queryset=None):
        return Collection.objects.live().get(slug=self.kwargs["collections_slug"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source_object"] = self.get_object

        return context
