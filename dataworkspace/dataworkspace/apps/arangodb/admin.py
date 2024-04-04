from django.contrib import admin
from dataworkspace.apps.arangodb.models import (
    SourceGraphCollection,
)
from dataworkspace.apps.arangodb.forms import (
    SourceGraphCollectionForm, 
    SourceGraphCollectionFieldDefinitionInline,
)


@admin.register(SourceGraphCollection)
class SourceGraphCollectionAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "collection",
        "dataset__name",
        "dataset__reference_code__code",
        "reference_number",
    ]
    form = SourceGraphCollectionForm
    exclude = ("reference_number",)
    readonly_fields = ("source_reference",)

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)

    inlines = [SourceGraphCollectionFieldDefinitionInline]
