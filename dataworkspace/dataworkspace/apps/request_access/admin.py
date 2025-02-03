from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe

from dataworkspace.apps.datasets.models import DataCutDataset, DataSet, VisualisationCatalogueItem
from dataworkspace.apps.request_access.models import AccessRequest


class AccessRequestAdmin(admin.ModelAdmin):
    exclude = ("catalogue_item_id", "id", "modified_date")

    def get_readonly_fields(self, request, obj=None):
        return ["journey", "catalogue_item"] + sorted(
            [field.name for field in self.opts.local_fields if field.name not in self.exclude]
        )

    def journey(self, obj):
        return obj.human_readable_journey

    @mark_safe
    def catalogue_item(self, obj):
        url = None
        catalogue_item = None

        if DataCutDataset.objects.filter(pk=obj.catalogue_item_id).exists():
            catalogue_item = DataCutDataset.objects.get(pk=obj.catalogue_item_id)
            url = reverse(
                "admin:datasets_datacutdataset_change",
                args=(catalogue_item.id,),
            )
        elif DataSet.objects.filter(pk=obj.catalogue_item_id).exists():
            catalogue_item = DataSet.objects.get(pk=obj.catalogue_item_id)
            url = reverse(
                "admin:datasets_masterdataset_change",
                args=(catalogue_item.id,),
            )
        elif VisualisationCatalogueItem.objects.filter(pk=obj.catalogue_item_id).exists():
            catalogue_item = VisualisationCatalogueItem.objects.get(pk=obj.catalogue_item_id)
            url = reverse(
                "admin:datasets_visualisationcatalogueitem_change",
                args=(catalogue_item.id,),
            )

        return '<a href="%s">%s</a>' % (url, catalogue_item)

    catalogue_item.allow_tags = True


admin.site.register(AccessRequest, AccessRequestAdmin)
