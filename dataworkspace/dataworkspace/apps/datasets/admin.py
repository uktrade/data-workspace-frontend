import logging

from adminsortable2.admin import SortableInlineAdminMixin
from django.contrib import admin
from django.contrib.admin.models import (
    LogEntry,
    CHANGE,
)
from django.contrib.contenttypes.models import (
    ContentType,
)
from django.db import (
    transaction,
)
from django.utils.encoding import (
    force_text,
)

from dataworkspace.apps.datasets.models import (
    DataGrouping,
    DataSet,
    SourceLink,
    SourceTable,
    ReferenceDataset,
    ReferenceDatasetField,
    CustomDatasetQuery,
    SourceView,
)
from dataworkspace.apps.core.admin import TimeStampedUserAdmin
from dataworkspace.apps.dw_admin.forms import (
    ReferenceDataFieldInlineForm,
    SourceLinkForm,
    DataSetForm,
    SourceLinkFormSet,
    ReferenceDataInlineFormset,
    ReferenceDatasetForm
)

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


class SourceTableInline(admin.TabularInline):
    model = SourceTable
    extra = 1


class SourceViewInline(admin.TabularInline):
    model = SourceView
    extra = 1


class CustomDatasetQueryInline(admin.TabularInline):
    model = CustomDatasetQuery
    extra = 0


@admin.register(DataSet)
class DataSetAdmin(admin.ModelAdmin):
    form = DataSetForm
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug', 'short_description', 'grouping', 'published')
    list_filter = ('grouping', )
    inlines = [
        SourceLinkInline,
        SourceTableInline,
        SourceViewInline,
        CustomDatasetQueryInline,
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
        original_user_access_type = obj.user_access_type
        obj.user_access_type = \
            'REQUIRES_AUTHORIZATION' if form.cleaned_data['requires_authorization'] else \
            'REQUIRES_AUTHENTICATION'
        super().save_model(request, obj, form, change)

        if original_user_access_type != obj.user_access_type:
            LogEntry.objects.log_action(
                user_id=request.user.pk, content_type_id=ContentType.objects.get_for_model(obj).pk,
                object_id=obj.id, object_repr=force_text(obj), action_flag=CHANGE,
                change_message='user_access_type set to {}'.format(obj.user_access_type),
            )


class ReferenceDataFieldInline(SortableInlineAdminMixin, admin.TabularInline):
    form = ReferenceDataFieldInlineForm
    formset = ReferenceDataInlineFormset
    model = ReferenceDatasetField
    fk_name = 'reference_dataset'
    min_num = 1
    extra = 1
    exclude = ['created_date', 'updated_date', 'created_by', 'updated_by']
    fieldsets = [
        (None, {
            'fields': [
                'name',
                'column_name',
                'data_type',
                'linked_reference_dataset',
                'description',
                'is_identifier',
                'is_display_name',
                'sort_order',
            ]
        })
    ]

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Do not allow a link between a reference dataset field and it's parent reference dataset
        if db_field.name == 'linked_reference_dataset':
            parent_id = request.resolver_match.kwargs.get('object_id')
            if parent_id is not None:
                kwargs['queryset'] = ReferenceDataset.objects.exclude(
                    id=parent_id
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ReferenceDataset)
class ReferenceDatasetAdmin(TimeStampedUserAdmin):
    form = ReferenceDatasetForm
    change_form_template = 'admin/reference_dataset_changeform.html'
    prepopulated_fields = {'slug': ('name',)}
    exclude = ['created_date', 'updated_date', 'created_by', 'updated_by', 'deleted']
    list_display = ('name', 'slug', 'short_description', 'group', 'published', 'version')
    inlines = [ReferenceDataFieldInline]
    fieldsets = [
        (None, {
            'fields': [
                'published',
                'is_joint_dataset',
                'name',
                'table_name',
                'slug',
                'group',
                'external_database',
                'short_description',
                'description',
                'valid_from',
                'valid_to',
                'enquiries_contact',
                'licence',
                'restrictions_on_usage',
                'sort_field',
                'sort_direction',
            ]
        })
    ]

    class Media:
        js = ('admin/js/vendor/jquery/jquery.js', 'data-workspace-admin.js',)

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

    def get_readonly_fields(self, request, obj=None):
        # Do not allow editing of table names via the admin
        if obj is not None:
            return self.readonly_fields + ('table_name',)
        return self.readonly_fields

    def save_formset(self, request, form, formset, change):
        for f in formset.forms:
            if not change:
                f.instance.created_by = request.user
            f.instance.updated_by = request.user
        super().save_formset(request, form, formset, change)
