import logging

from django import forms
from django.contrib import admin
from django.db import (
    transaction,
)

from dataworkspace.apps.datasets.models import (
    DataGrouping,
    DataSet,
    SourceLink,
    SourceTable,
    ReferenceDataset,
    ReferenceDatasetField
)
from dataworkspace.apps.core.admin import TimeStampedUserAdmin
from dataworkspace.apps.dw_admin.forms import (ReferenceDataFieldInlineForm, SourceLinkForm, DataSetForm,
                                               SourceLinkFormSet)

logger = logging.getLogger('app')


@admin.register(DataGrouping)
class DataGroupingAdmin(TimeStampedUserAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug', 'short_description')
    exclude = ['created_date', 'updated_date', 'created_by', 'updated_by', 'deleted']

    def get_queryset(self, request):
        # Only show non-deleted groups in admin
        return self.model.objects.live()


class DataLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'format', 'url', 'dataset')


class SourceLinkInline(admin.TabularInline):
    template = 'admin/source_link_inline.html'
    form = SourceLinkForm
    formset = SourceLinkFormSet
    model = SourceLink
    extra = 1


class SourceTableInline(admin.StackedInline):
    model = SourceTable
    extra = 1


@admin.register(DataSet)
class DataSetAdmin(admin.ModelAdmin):
    form = DataSetForm
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug', 'short_description', 'grouping', 'published')
    list_filter = ('grouping', )
    inlines = [
        SourceLinkInline,
        SourceTableInline,
    ]
    fieldsets = [
        (None, {
            'fields': [
                'published',
                'name',
                'slug',
                'short_description',
                'grouping',
                'description',
                'enquiries_contact',
                'redactions',
                'licence',
                'volume',
                'retention_policy',
                'personal_data',
                'restrictions_on_usage',
            ]
        }),
        ('Permissions', {
            'fields': [
                'requires_authorization',
            ]
        })
    ]

    class Media:
        css = {
            'all': ('data-workspace-admin.css',)
        }

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        obj.user_access_type = \
            'REQUIRES_AUTHORIZATION' if form.cleaned_data['requires_authorization'] else \
            'REQUIRES_AUTHENTICATION'

        super().save_model(request, obj, form, change)


class ReferenceDataInlineFormset(forms.BaseInlineFormSet):
    model = ReferenceDatasetField

    def clean(self):
        # Ensure one and only one field is set as identifier
        identifiers = [
            x for x in self.forms
            if x.cleaned_data.get('is_identifier') and not x.cleaned_data['DELETE']
        ]
        if not identifiers:
            raise forms.ValidationError(
                'Please ensure one field is set as the unique identifier'
            )
        if len(identifiers) > 1:
            raise forms.ValidationError(
                'Please select only one unique identifier field'
            )


class ReferenceDataFieldInline(admin.TabularInline):
    form = ReferenceDataFieldInlineForm
    formset = ReferenceDataInlineFormset
    model = ReferenceDatasetField
    min_num = 1
    extra = 1
    exclude = ['created_date', 'updated_date', 'created_by', 'updated_by', 'deleted']
    fieldsets = [
        (None, {
            'fields': [
                'name',
                'data_type',
                'description',
                'is_identifier'
            ]
        })
    ]


@admin.register(ReferenceDataset)
class ReferenceDatasetAdmin(TimeStampedUserAdmin):
    change_form_template = 'admin/reference_dataset_changeform.html'
    prepopulated_fields = {'slug': ('name',)}
    exclude = ['created_date', 'updated_date', 'created_by', 'updated_by', 'deleted']
    list_display = ('name', 'slug', 'short_description', 'group', 'published', 'version')
    inlines = [ReferenceDataFieldInline]
    fieldsets = [
        (None, {
            'fields': [
                'published',
                'name',
                'slug',
                'group',
                'short_description',
                'description',
                'valid_from',
                'valid_to',
                'enquiries_contact',
                'licence',
                'restrictions_on_usage',
            ]
        })
    ]

    def get_queryset(self, request):
        # Only show non-deleted reference datasets in admin
        return self.model.objects.live()

    def get_actions(self, request):
        """
        Disable bulk delete so tables can be managed.
        :param request:
        :return:
        """
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def save_formset(self, request, form, formset, change):
        for f in formset.forms:
            if not change:
                f.instance.created_by = request.user
            f.instance.updated_by = request.user
        super().save_formset(request, form, formset, change)
