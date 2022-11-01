from django.http import Http404
from django.views.generic import DetailView

from dataworkspace.apps.data_collections.models import Collection


def get_authorised_collection(request, collection_id):
    collection_object = Collection.objects.live().get(id=collection_id)
    if request.user.is_superuser or (
        collection_object.published and request.user == collection_object.owner
    ):
        return collection_object
    else:
        raise Http404


class CollectionsDetailView(DetailView):
    template_name = "data_collections/collection_detail.html"

    def get_object(self, queryset=None):
        return get_authorised_collection(self.request, self.kwargs["collections_id"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        source_object = self.get_object()
        context["source_object"] = source_object
        context["dataset_collections"] = source_object.dataset_collections.all()

        return context
