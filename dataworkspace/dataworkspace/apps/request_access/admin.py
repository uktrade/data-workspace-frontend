from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe

from dataworkspace.apps.datasets.models import DataSet, VisualisationCatalogueItem
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
        try:
            catalogue_item = DataSet.objects.get(pk=obj.catalogue_item_id)
        except DataSet.DoesNotExist:
            try:
                catalogue_item = VisualisationCatalogueItem.objects.get(pk=obj.catalogue_item_id)
            except VisualisationCatalogueItem.DoesNotExist:
                return None
            else:
                url = reverse(
                    "admin:datasets_visualisationcatalogueitem_change",
                    args=(catalogue_item.id,),
                )
        else:
            url = reverse("admin:datasets_masterdataset_change", args=(catalogue_item.id,))

        return '<a href="%s">%s</a>' % (url, catalogue_item)

    catalogue_item.allow_tags = True


admin.site.register(AccessRequest, AccessRequestAdmin)
