from django.contrib import admin
from dataworkspace.apps.datasets.models import (
    ArangoDocumentCollection,
)
from dataworkspace.apps.arangodb.forms import (
    ArangoDocumentCollectionForm,
    ArangoDocumentCollectionFieldDefinitionInline,
)


@admin.register(ArangoDocumentCollection)
class ArangoDocumentCollectionAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "collection",
        "dataset__name",
        "dataset__reference_code__code",
        "reference_number",
    ]
    form = ArangoDocumentCollectionForm
    exclude = ("reference_number",)
    readonly_fields = ("source_reference",)

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)

    inlines = [ArangoDocumentCollectionFieldDefinitionInline]
