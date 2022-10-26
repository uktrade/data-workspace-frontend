from django.http import Http404
from django.views.generic import DetailView

from dataworkspace.apps.data_collections.models import Collection


class CollectionsDetailView(DetailView):
    template_name = "data_collections/collection_detail.html"

    def get_object(self, queryset=None):
        collection_object = Collection.objects.live().get(slug=self.kwargs["collections_slug"])
        if self.request.user.is_superuser or (
            collection_object.published and self.request.user == collection_object.owner
        ):
            return collection_object
        else:
            raise Http404

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source_object"] = self.get_object

        return context
