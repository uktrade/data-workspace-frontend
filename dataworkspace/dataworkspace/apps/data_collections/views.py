from django.shortcuts import render

from django.views.generic import DetailView

from dataworkspace.apps.data_collections.models import Collection


class CollectionsDetailView(DetailView):
    def get_object(self, queryset=None):
        return Collection.objects.live().get(slug=self.kwargs["collections_slug"])
