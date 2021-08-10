from django.contrib import admin
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe

from dataworkspace.apps.datasets.models import DataSet, VisualisationCatalogueItem
from dataworkspace.apps.request_access.models import AccessRequest


class AccessRequestAdmin(admin.ModelAdmin):

    exclude = ('catalogue_item_id', 'training_screenshot', 'id', 'modified_date')

    def get_readonly_fields(self, request, obj=None):
        return ['journey', 'catalogue_item', 'training_screenshot_image'] + sorted(
            list(
                set(
                    [
                        field.name
                        for field in self.opts.local_fields
                        if field.name not in self.exclude
                    ]
                )
            )
        )

    @mark_safe
    def catalogue_item(self, obj):
        try:
            catalogue_item = DataSet.objects.get(pk=obj.catalogue_item_id)
        except DataSet.DoesNotExist:
            try:
                catalogue_item = VisualisationCatalogueItem.objects.get(
                    pk=obj.catalogue_item_id
                )
            except VisualisationCatalogueItem.DoesNotExist:
                return None
            else:
                url = reverse(
                    'admin:datasets_visualisationcatalogueitem_change',
                    args=(catalogue_item.id,),
                )
        else:
            url = reverse(
                'admin:datasets_masterdataset_change', args=(catalogue_item.id,)
            )

        return '<a href="%s">%s</a>' % (url, catalogue_item)

    catalogue_item.allow_tags = True

    @mark_safe
    def training_screenshot_image(self, obj):
        return u'<img src="%s" />' % escape(obj.training_screenshot.url)

    training_screenshot_image.allow_tags = True


admin.site.register(AccessRequest, AccessRequestAdmin)
