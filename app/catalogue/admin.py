from django.contrib import admin

from catalogue.models import (
    DataGrouping,
    DataSet,
    ResponsiblePerson,
    DataLink,
)

admin.site.site_header = 'Data Catalogue'


class DataGroupingAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ('name', 'slug', 'short_description')


class DataSetAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ('name', 'slug', 'short_description', 'grouping')


class DataLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'format', 'url', 'dataset')


admin.site.register(ResponsiblePerson)
admin.site.register(DataGrouping, DataGroupingAdmin)
admin.site.register(DataSet, DataSetAdmin)
admin.site.register(DataLink, DataLinkAdmin)
