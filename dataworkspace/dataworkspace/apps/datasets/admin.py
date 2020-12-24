import csv
import logging
from datetime import datetime

from adminsortable2.admin import SortableInlineAdminMixin
from csp.decorators import csp_update
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from django.urls import reverse

from dataworkspace.apps.applications.models import VisualisationTemplate
from dataworkspace.apps.applications.utils import sync_quicksight_permissions
from dataworkspace.apps.core.admin import DeletableTimeStampedUserAdmin
from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    DataCutDataset,
    DataSetUserPermission,
    DatasetReferenceCode,
    MasterDataset,
    ReferenceDataset,
    ReferenceDatasetField,
    SourceLink,
    SourceTable,
    SourceView,
    Tag,
    VisualisationCatalogueItem,
    VisualisationUserPermission,
    VisualisationLink,
    ToolQueryAuditLog,
)
from dataworkspace.apps.dw_admin.forms import (
    CustomDatasetQueryForm,
    DataCutDatasetForm,
    MasterDatasetForm,
    ReferenceDataFieldInlineForm,
    ReferenceDataInlineFormset,
    ReferenceDatasetForm,
    SourceLinkForm,
    SourceTableForm,
    SourceViewForm,
    CustomDatasetQueryInlineForm,
    VisualisationCatalogueItemForm,
    VisualisationLinkForm,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_permission_change
from dataworkspace.apps.explorer.schema import clear_schema_info_cache_for_user

logger = logging.getLogger('app')


class CSPRichTextEditorMixin:

    # We allow inline scripts to run on this page in order to support CKEditor,
    # which gives rich-text formatting but unfortunately uses inline scripts to
    # do so - and we don't have a clean way to either hash the inline script on-demand
    # or inject our request CSP nonce.
    @csp_update(SCRIPT_SRC="'unsafe-inline'")
    def add_view(self, request, form_url='', extra_context=None):
        return super().add_view(request, form_url, extra_context)

    @csp_update(SCRIPT_SRC="'unsafe-inline'")
    def change_view(self, request, object_id, form_url='', extra_context=None):
        return super().change_view(request, object_id, form_url, extra_context)


class DataLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'format', 'url', 'dataset')


class ManageUnpublishedDatasetsMixin(BaseModelAdmin):
    """
    This class gets mixed in with ModelAdmin subclasses that are used to manage datasets. This
    can be the main dataset ModelAdmin or the ModelAdmins used for additional (meta)data, e.g.
    CustomDatasetQueryInline.
    """

    manage_unpublished_permission_codename = None

    def __init__(self, *args, **kwargs):
        if self.manage_unpublished_permission_codename is None:
            raise NotImplementedError(
                "Must define class attribute `manage_unpublished_permission_codename`"
            )
        super().__init__(*args, **kwargs)

    def has_add_permission(self, request):
        if request.user.has_perm(self.manage_unpublished_permission_codename):
            return True

        return super().has_add_permission(request)

    def has_view_permission(self, request, obj=None):
        if request.user.has_perm(self.manage_unpublished_permission_codename):
            return True

        return super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        native_perms = super().has_view_permission(request, obj)

        if request.user.has_perm(self.manage_unpublished_permission_codename):
            if obj and hasattr(obj, 'published'):
                return not obj.published or native_perms

            return True

        return native_perms


class SourceReferenceInlineMixin(ManageUnpublishedDatasetsMixin):
    readonly_fields = ('source_reference',)
    exclude = ('reference_number',)

    def source_reference(self, instance):
        code = instance.source_reference
        if code is not None:
            return code
        return '-'


class SourceLinkInline(admin.TabularInline, SourceReferenceInlineMixin):
    template = 'admin/source_link_inline.html'
    form = SourceLinkForm
    model = SourceLink
    extra = 1
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_datacut_datasets'
    )


class SourceTableInline(admin.TabularInline, SourceReferenceInlineMixin):
    model = SourceTable
    extra = 1
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_master_datasets'
    )


class SourceViewInline(admin.TabularInline, SourceReferenceInlineMixin):
    model = SourceView
    extra = 1
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_datacut_datasets'
    )


class CustomDatasetQueryInline(admin.TabularInline, SourceReferenceInlineMixin):
    model = CustomDatasetQuery
    form = CustomDatasetQueryInlineForm
    extra = 0
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_datacut_datasets'
    )
    readonly_fields = ('tables',)

    def tables(self, obj):
        if not obj.pk:
            return ''
        tables = obj.tables.all()
        if not tables:
            return 'No tables found in query.\n\nPlease ensure the SQL is valid and that the tables exist'
        return '\n'.join([f'"{t.schema}"."{t.table}"' for t in obj.tables.all()])

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)

        # SQL queries should be reviewed by a superuser
        extra_readonly = set()
        if not request.user.is_superuser and request.user.has_perm(
            self.manage_unpublished_permission_codename
        ):
            extra_readonly.add('reviewed')

        readonly_fields = readonly_fields + tuple(extra_readonly)

        return readonly_fields


def clone_dataset(modeladmin, request, queryset):
    for dataset in queryset:
        dataset.clone()


class PermissionedDatasetAdmin(
    DeletableTimeStampedUserAdmin, ManageUnpublishedDatasetsMixin
):
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)

        # Don't allow users who can only manage unpublished datasets, to publish a dataset
        extra_readonly = []
        if not request.user.is_superuser and request.user.has_perm(
            self.manage_unpublished_permission_codename
        ):
            extra_readonly.append('published')

        readonly_fields = readonly_fields + tuple(extra_readonly)

        return readonly_fields


class BaseDatasetAdmin(PermissionedDatasetAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = (
        'name',
        'slug',
        'short_description',
        'get_tags',
        'published',
        'number_of_downloads',
    )
    list_filter = ('tags',)
    search_fields = ['name']
    actions = [clone_dataset]
    autocomplete_fields = ['tags']
    fieldsets = [
        (
            None,
            {
                'fields': [
                    'published',
                    'name',
                    'slug',
                    'tags',
                    'reference_code',
                    'short_description',
                    'description',
                    'enquiries_contact',
                    'information_asset_owner',
                    'information_asset_manager',
                    'licence',
                    'retention_policy',
                    'personal_data',
                    'restrictions_on_usage',
                    'type',
                ]
            },
        ),
        (
            'Permissions',
            {
                'fields': [
                    'requires_authorization',
                    'eligibility_criteria',
                    'authorized_users',
                ]
            },
        ),
    ]

    class Media:
        js = ('js/min/django_better_admin_arrayfield.min.js',)
        css = {
            'all': (
                'css/min/django_better_admin_arrayfield.min.css',
                'data-workspace-admin.css',
            )
        }

    def get_tags(self, obj):
        return ', '.join([x.name for x in obj.tags.all()])

    get_tags.short_description = 'Tags'

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        original_user_access_type = obj.user_access_type
        obj.user_access_type = (
            'REQUIRES_AUTHORIZATION'
            if form.cleaned_data['requires_authorization']
            else 'REQUIRES_AUTHENTICATION'
        )

        current_authorized_users = set(
            get_user_model().objects.filter(datasetuserpermission__dataset=obj)
        )

        authorized_users = set(
            form.cleaned_data.get('authorized_users', get_user_model().objects.none())
        )

        super().save_model(request, obj, form, change)

        changed_user_sso_ids = set()

        clear_schema_info_cache = False
        for user in authorized_users - current_authorized_users:
            DataSetUserPermission.objects.create(dataset=obj, user=user)
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_GRANTED_DATASET_PERMISSION,
                {'for_user_id': user.id},
                f"Added dataset {obj} permission",
            )
            changed_user_sso_ids.add(str(user.profile.sso_id))
            clear_schema_info_cache = True

        for user in current_authorized_users - authorized_users:
            DataSetUserPermission.objects.filter(dataset=obj, user=user).delete()
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_REVOKED_DATASET_PERMISSION,
                {'for_user_id': user.id},
                f"Removed dataset {obj} permission",
            )
            changed_user_sso_ids.add(str(user.profile.sso_id))
            clear_schema_info_cache = True

        if clear_schema_info_cache:
            clear_schema_info_cache_for_user(user)

        if original_user_access_type != obj.user_access_type:
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_SET_DATASET_USER_ACCESS_TYPE,
                {"access_type": obj.user_access_type},
                f"user_access_type set to {obj.user_access_type}",
            )

        if isinstance(self, MasterDatasetAdmin):
            if changed_user_sso_ids:
                sync_quicksight_permissions.delay(
                    user_sso_ids_to_update=tuple(changed_user_sso_ids)
                )
            elif original_user_access_type != obj.user_access_type:
                sync_quicksight_permissions.delay()


@admin.register(MasterDataset)
class MasterDatasetAdmin(CSPRichTextEditorMixin, BaseDatasetAdmin):
    form = MasterDatasetForm
    inlines = [SourceTableInline]
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_master_datasets'
    )


@admin.register(DataCutDataset)
class DataCutDatasetAdmin(CSPRichTextEditorMixin, BaseDatasetAdmin):
    form = DataCutDatasetForm
    inlines = [SourceLinkInline, SourceViewInline, CustomDatasetQueryInline]
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_datacut_datasets'
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    fields = ['type', 'name']
    search_fields = ['name']
    list_filter = ['type']

    def get_search_results(self, request, queryset, search_term):
        """
        Override to allow autocomplete search to work with tag type as well as tag name
        """
        search_term = search_term.lower()
        queryset, use_distinct = super().get_search_results(
            request, queryset, search_term
        )
        type_choices = {b.lower(): a for a, b in Tag._TYPE_CHOICES}

        if search_term in type_choices:
            queryset |= self.model.objects.filter(type=type_choices[search_term])
        return queryset, use_distinct


class ReferenceDataFieldInline(
    SortableInlineAdminMixin, admin.TabularInline, ManageUnpublishedDatasetsMixin
):
    form = ReferenceDataFieldInlineForm
    formset = ReferenceDataInlineFormset
    model = ReferenceDatasetField
    fk_name = 'reference_dataset'
    min_num = 1
    extra = 1
    exclude = ['created_date', 'updated_date', 'created_by', 'updated_by']
    fieldsets = [
        (
            None,
            {
                'fields': [
                    'name',
                    'data_type',
                    'column_name',
                    'relationship_name',
                    'linked_reference_dataset_field',
                    'description',
                    'is_identifier',
                    'is_display_name',
                    'sort_order',
                ]
            },
        )
    ]
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_reference_datasets'
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Do not allow a link between a reference dataset field and it's parent reference dataset
        if db_field.name == 'linked_reference_dataset_field':
            parent_id = request.resolver_match.kwargs.get('object_id')
            if parent_id is not None:
                kwargs['queryset'] = ReferenceDatasetField.objects.exclude(
                    reference_dataset__id=parent_id
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ReferenceDataset)
class ReferenceDatasetAdmin(CSPRichTextEditorMixin, PermissionedDatasetAdmin):
    form = ReferenceDatasetForm
    change_form_template = 'admin/reference_dataset_changeform.html'
    prepopulated_fields = {'slug': ('name',)}
    list_display = (
        'name',
        'slug',
        'short_description',
        'get_published_version',
        'published_at',
        'published',
    )
    inlines = [ReferenceDataFieldInline]
    autocomplete_fields = ['tags']
    fieldsets = [
        (
            None,
            {
                'fields': [
                    'published',
                    'get_published_version',
                    'name',
                    'table_name',
                    'slug',
                    'tags',
                    'external_database',
                    'short_description',
                    'description',
                    'valid_from',
                    'valid_to',
                    'enquiries_contact',
                    'information_asset_owner',
                    'information_asset_manager',
                    'licence',
                    'restrictions_on_usage',
                    'sort_field',
                    'sort_direction',
                ]
            },
        )
    ]
    readonly_fields = ('get_published_version',)
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_reference_datasets'
    )

    def get_published_version(self, obj):
        if obj.published_version == '0.0':
            return ' - '
        return obj.published_version

    get_published_version.short_description = 'Version'

    class Media:
        js = ('admin/js/vendor/jquery/jquery.js', 'data-workspace-admin.js')

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)

        # Do not allow editing of table names via the admin
        if obj is not None:
            return readonly_fields + ('table_name',)

        return readonly_fields

    def save_formset(self, request, form, formset, change):
        for f in formset.forms:
            if not change:
                f.instance.created_by = request.user
            f.instance.updated_by = request.user
        super().save_formset(request, form, formset, change)


@admin.register(CustomDatasetQuery)
class CustomDatasetQueryAdmin(admin.ModelAdmin):
    search_fields = [
        'name',
        'query',
        'dataset__name',
        'dataset__reference_code__code',
        'reference_number',
    ]
    form = CustomDatasetQueryForm
    exclude = ('reference_number',)
    readonly_fields = ('source_reference',)
    actions = ['export_queries']

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)

    def export_queries(self, request, queryset):
        field_names = ['dataset_name', 'query_name', 'query_admin_url', 'query']
        response = HttpResponse(content_type='text/csv')
        response[
            'Content-Disposition'
        ] = 'attachment; filename=dataset-queries-{}.csv'.format(
            datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        )
        writer = csv.DictWriter(response, field_names, quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        for query in queryset:
            writer.writerow(
                {
                    'dataset_name': query.dataset.name,
                    'query_name': query.name,
                    'query_admin_url': request.build_absolute_uri(
                        reverse(
                            'admin:datasets_customdatasetquery_change', args=(query.id,)
                        )
                    ),
                    'query': query.query,
                }
            )
        return response

    export_queries.short_description = 'Export Selected'


@admin.register(SourceView)
class SourceViewAdmin(admin.ModelAdmin):
    search_fields = [
        'name',
        'view',
        'dataset__name',
        'dataset__reference_code__code',
        'reference_number',
    ]
    form = SourceViewForm
    exclude = ('reference_number',)
    readonly_fields = ('source_reference',)

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)


@admin.register(SourceTable)
class SourceTableAdmin(admin.ModelAdmin):
    search_fields = [
        'name',
        'table',
        'dataset__name',
        'dataset__reference_code__code',
        'reference_number',
    ]
    form = SourceTableForm
    exclude = ('reference_number',)
    readonly_fields = ('source_reference',)

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)


class VisualisationLinkInline(admin.TabularInline, ManageUnpublishedDatasetsMixin):
    form = VisualisationLinkForm
    model = VisualisationLink
    extra = 1
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_visualisations'
    )


@admin.register(VisualisationCatalogueItem)
class VisualisationCatalogueItemAdmin(
    CSPRichTextEditorMixin, DeletableTimeStampedUserAdmin
):
    form = VisualisationCatalogueItemForm
    list_display = (
        'name',
        'short_description',
        'published',
        'get_tags',
    )
    list_filter = ('tags',)
    search_fields = ['name']
    autocomplete_fields = ['tags']
    fieldsets = [
        (
            None,
            {
                'fields': [
                    'published',
                    'name',
                    'slug',
                    'tags',
                    'short_description',
                    'description',
                    'enquiries_contact',
                    'secondary_enquiries_contact',
                    'information_asset_owner',
                    'information_asset_manager',
                    'licence',
                    'retention_policy',
                    'personal_data',
                    'restrictions_on_usage',
                ]
            },
        ),
        (
            'Permissions',
            {
                'fields': [
                    'requires_authorization',
                    'eligibility_criteria',
                    'authorized_users',
                ]
            },
        ),
        ('GitLab visualisation', {'fields': ['visualisation_template']}),
    ]
    inlines = [VisualisationLinkInline]

    class Media:
        js = ('js/min/django_better_admin_arrayfield.min.js', 'data-workspace-admin.js')
        css = {
            'all': (
                'css/min/django_better_admin_arrayfield.min.css',
                'data-workspace-admin.css',
            )
        }

    def get_tags(self, obj):
        return ', '.join([x.name for x in obj.tags.all()])

    get_tags.short_description = 'Tags'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "visualisation_template":
            kwargs["queryset"] = VisualisationTemplate.objects.filter(
                application_type='VISUALISATION'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if obj.visualisation_template and not obj.name:
            obj.name = obj.visualisation_template.nice_name

        original_user_access_type = obj.user_access_type
        obj.user_access_type = (
            'REQUIRES_AUTHORIZATION'
            if form.cleaned_data['requires_authorization']
            else 'REQUIRES_AUTHENTICATION'
        )

        current_authorized_users = set(
            get_user_model().objects.filter(
                visualisationuserpermission__visualisation=obj
            )
        )

        authorized_users = set(
            form.cleaned_data.get('authorized_users', get_user_model().objects.none())
        )

        super().save_model(request, obj, form, change)

        for user in authorized_users - current_authorized_users:
            VisualisationUserPermission.objects.create(visualisation=obj, user=user)
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_GRANTED_VISUALISATION_PERMISSION,
                {'for_user_id': user.id},
                f"Added visualisation {obj} permission",
            )

        for user in current_authorized_users - authorized_users:
            VisualisationUserPermission.objects.filter(
                visualisation=obj, user=user
            ).delete()
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_REVOKED_VISUALISATION_PERMISSION,
                {'for_user_id': user.id},
                f"Removed visualisation {obj} permission",
            )

        if original_user_access_type != obj.user_access_type:
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_SET_DATASET_USER_ACCESS_TYPE,
                {"access_type": obj.user_access_type},
                f"user_access_type set to {obj.user_access_type}",
            )


@admin.register(DatasetReferenceCode)
class DatasetReferenceCodeAdmin(admin.ModelAdmin):
    search_fields = ['code', 'description']
    fields = ['code', 'description']


@admin.register(ToolQueryAuditLog)
class ToolQueryAuditLogAdmin(admin.ModelAdmin):
    search_fields = ['user__email', 'rolename', 'query_sql']
    fields = [
        'id',
        'timestamp',
        'user',
        'database',
        'rolename',
        'get_detail_truncated_query',
    ]
    list_display = [
        'id',
        'timestamp',
        'user',
        'database',
        'rolename',
        'get_list_truncated_query',
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def _truncate_query(self, query, length):
        if len(query) > length:
            return query[:length] + '...'
        return query

    def get_list_truncated_query(self, obj):
        return self._truncate_query(
            obj.query_sql, settings.TOOL_QUERY_LOG_ADMIN_LIST_QUERY_TRUNC_LENGTH
        )

    get_list_truncated_query.short_description = 'Query SQL'

    def get_detail_truncated_query(self, obj):
        return self._truncate_query(
            obj.query_sql, settings.TOOL_QUERY_LOG_ADMIN_DETAIL_QUERY_TRUNC_LENGTH
        )

    get_detail_truncated_query.short_description = 'Query SQL'
