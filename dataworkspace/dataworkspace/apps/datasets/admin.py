import csv
import functools
import logging
from datetime import datetime

from adminsortable2.admin import SortableInlineAdminMixin
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import format_html

from dataworkspace.apps.api_v1.core.views import (
    invalidate_superset_user_cached_credentials,
    remove_superset_user_cached_credentials,
)
from dataworkspace.apps.applications.models import VisualisationTemplate
from dataworkspace.apps.applications.utils import sync_quicksight_permissions
from dataworkspace.apps.core.admin import (
    DeletableTimeStampedUserAdmin,
    DeletableTimeStampedUserTabularInline,
    CSPRichTextEditorMixin,
)
from dataworkspace.apps.datasets.constants import TagType
from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    DataCutDataset,
    DataSetUserPermission,
    DataSetVisualisation,
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
    DataSetVisualisationForm,
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
from dataworkspace.apps.explorer.utils import (
    invalidate_data_explorer_user_cached_credentials,
    remove_data_explorer_user_cached_credentials,
)

logger = logging.getLogger('app')


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
    form = SourceTableForm
    extra = 1
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_master_datasets'
    )


class DataSetVisualisationInline(DeletableTimeStampedUserTabularInline):
    model = DataSetVisualisation
    form = DataSetVisualisationForm
    extra = 1
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_master_datasets'
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(deleted=False)


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
        'get_bookmarks',
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
                    'licence_url',
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
                    'open_to_all_users',
                    'eligibility_criteria',
                    'authorized_email_domains',
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

    def get_form(self, request, obj=None, **kwargs):  # pylint: disable=W0221
        form_class = super().get_form(request, obj=None, **kwargs)
        form_class.base_fields['authorized_email_domains'].widget.attrs[
            'style'
        ] = 'width: 30em;'
        form_class.base_fields['eligibility_criteria'].widget.attrs[
            'style'
        ] = 'width: 30em;'
        return functools.partial(form_class, user=request.user)

    def get_tags(self, obj):
        return ', '.join([x.name for x in obj.tags.all()])

    get_tags.short_description = 'Tags'

    def get_bookmarks(self, obj):
        return obj.bookmark_count()

    get_bookmarks.admin_order_field = 'datasetbookmark'
    get_bookmarks.short_description = 'Bookmarks'

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        original_user_access_type = obj.user_access_type

        obj.user_access_type = (
            'REQUIRES_AUTHENTICATION'
            if form.cleaned_data['open_to_all_users']
            else 'REQUIRES_AUTHORIZATION'
        )

        current_authorized_users = set(
            get_user_model().objects.filter(datasetuserpermission__dataset=obj)
        )

        authorized_users = set(
            form.cleaned_data.get('authorized_users', get_user_model().objects.none())
        )

        super().save_model(request, obj, form, change)

        changed_users = set()

        for user in authorized_users - current_authorized_users:
            DataSetUserPermission.objects.create(dataset=obj, user=user)
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_GRANTED_DATASET_PERMISSION,
                {'for_user_id': user.id},
                f"Added dataset {obj} permission",
            )
            changed_users.add(user)
            clear_schema_info_cache_for_user(user)

        for user in current_authorized_users - authorized_users:
            DataSetUserPermission.objects.filter(dataset=obj, user=user).delete()
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_REVOKED_DATASET_PERMISSION,
                {'for_user_id': user.id},
                f"Removed dataset {obj} permission",
            )
            changed_users.add(user)
            clear_schema_info_cache_for_user(user)

        if (
            original_user_access_type != obj.user_access_type
            or 'authorized_email_domains' in form.changed_data
        ):
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_SET_DATASET_USER_ACCESS_TYPE
                if original_user_access_type != obj.user_access_type
                else EventLog.TYPE_CHANGED_AUTHORIZED_EMAIL_DOMAIN,
                {"access_type": obj.user_access_type},
                f"user_access_type set to {obj.user_access_type}",
            )

            # As the dataset's access type has changed, clear cached credentials for all
            # users to ensure they either:
            #   - lose access if it went from REQUIRES_AUTHENTICATION to REQUIRES_AUTHORIZATION
            #   - get access if it went from REQUIRES_AUTHORIZATION to REQUIRES_AUTHENTICATION
            invalidate_data_explorer_user_cached_credentials()
            invalidate_superset_user_cached_credentials()
        else:
            for user in changed_users:
                remove_data_explorer_user_cached_credentials(user)
                remove_superset_user_cached_credentials(user)

        if isinstance(self, MasterDatasetAdmin):
            if changed_users:
                # If we're changing permissions for loads of users, let's just do a full quicksight re-sync.
                # Makes fewer AWS calls and probably completes as quickly if not quicker.
                if len(changed_users) >= 50:
                    sync_quicksight_permissions.delay()
                else:
                    changed_user_sso_ids = [
                        str(u.profile.sso_id) for u in changed_users
                    ]
                    sync_quicksight_permissions.delay(
                        user_sso_ids_to_update=tuple(changed_user_sso_ids)
                    )
            elif original_user_access_type != obj.user_access_type:
                sync_quicksight_permissions.delay()


@admin.register(MasterDataset)
class MasterDatasetAdmin(CSPRichTextEditorMixin, BaseDatasetAdmin):
    form = MasterDatasetForm
    inlines = [SourceTableInline, DataSetVisualisationInline]
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_master_datasets'
    )

    def save_formset(self, request, form, formset, change):
        if formset.model != DataSetVisualisation:
            super().save_formset(request, form, formset, change)
        else:
            instances = formset.save(commit=False)
            # Save any changes
            for instance in instances:
                if not instance.pk:
                    instance.created_by = request.user
                instance.updated_by = request.user
                instance.save()
            # Soft delete any deletions
            for instance in formset.deleted_objects:
                instance.deleted = True
                instance.save()

            formset.save_m2m()


@admin.register(DataCutDataset)
class DataCutDatasetAdmin(CSPRichTextEditorMixin, BaseDatasetAdmin):
    form = DataCutDatasetForm
    inlines = [
        SourceLinkInline,
        SourceViewInline,
        CustomDatasetQueryInline,
    ]
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
        type_choices = {b.lower(): a for a, b in TagType.choices}

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
        'get_bookmarks',
    )
    inlines = [ReferenceDataFieldInline]
    autocomplete_fields = ['tags']
    autocomplete_fields = (
        'enquiries_contact',
        'information_asset_owner',
        'information_asset_manager',
    )
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

    def get_bookmarks(self, obj):
        return obj.bookmark_count()

    get_bookmarks.admin_order_field = 'referencedatasetbookmark'
    get_bookmarks.short_description = 'Bookmarks'

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
        'get_bookmarks',
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
                    'open_to_all_users',
                    'eligibility_criteria',
                    'authorized_email_domains',
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

    def get_form(self, request, obj=None, **kwargs):  # pylint: disable=W0221
        form_class = super().get_form(request, obj=None, **kwargs)
        form_class.base_fields['authorized_email_domains'].widget.attrs[
            'style'
        ] = 'width: 30em;'
        form_class.base_fields['eligibility_criteria'].widget.attrs[
            'style'
        ] = 'width: 30em;'
        return functools.partial(form_class, user=request.user)

    def get_tags(self, obj):
        return ', '.join([x.name for x in obj.tags.all()])

    get_tags.short_description = 'Tags'

    def get_bookmarks(self, obj):
        return obj.bookmark_count()

    get_bookmarks.admin_order_field = 'visualisationbookmark'
    get_bookmarks.short_description = 'Bookmarks'

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
            'REQUIRES_AUTHENTICATION'
            if form.cleaned_data['open_to_all_users']
            else 'REQUIRES_AUTHORIZATION'
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

        changed_users = set()

        for user in authorized_users - current_authorized_users:
            VisualisationUserPermission.objects.create(visualisation=obj, user=user)
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_GRANTED_VISUALISATION_PERMISSION,
                {'for_user_id': user.id},
                f"Added visualisation {obj} permission",
            )
            changed_users.add(user)

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
            changed_users.add(user)

        if (
            original_user_access_type != obj.user_access_type
            or 'authorized_email_domains' in form.changed_data
        ):
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_SET_DATASET_USER_ACCESS_TYPE
                if original_user_access_type != obj.user_access_type
                else EventLog.TYPE_CHANGED_AUTHORIZED_EMAIL_DOMAIN,
                {"access_type": obj.user_access_type},
                f"user_access_type set to {obj.user_access_type}",
            )

            # As the visualisation's access type has changed, clear cached credentials for all
            # users to ensure they either:
            #   - lose access if it went from REQUIRES_AUTHENTICATION to REQUIRES_AUTHORIZATION
            #   - get access if it went from REQUIRES_AUTHORIZATION to REQUIRES_AUTHENTICATION
            invalidate_superset_user_cached_credentials()
        else:
            for user in changed_users:
                remove_superset_user_cached_credentials(user)


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
        'get_user_name_link',
        'user',
        'rolename',
        'database',
        'get_detail_truncated_query',
        'get_detail_related_datasets',
    ]
    list_display = [
        'timestamp',
        'get_user_email_link',
        'database',
        'rolename',
        'get_list_truncated_query',
        'get_list_related_datasets',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_tables = SourceTable.objects.filter(dataset__deleted=False)
        self.reference_datasets = ReferenceDataset.objects.live()

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

    def _get_user_link(self, obj):
        return reverse("admin:auth_user_change", args=(obj.user.id,))

    def get_user_email_link(self, obj):
        return format_html(f'<a href="{self._get_user_link(obj)}">{obj.user.email}</a>')

    def get_user_name_link(self, obj):
        return format_html(
            f'<a href="{self._get_user_link(obj)}">{obj.user.get_full_name()}</a>'
        )

    get_user_name_link.short_description = 'User'

    def _get_related_datasets(self, obj, separator):
        datasets = set()
        for table in obj.tables.all():
            for source_table in self.source_tables.filter(
                schema=table.schema, table=table.table
            ):
                datasets.add(source_table.dataset)
            if table.schema == 'public':
                for ref_dataset in self.reference_datasets.filter(
                    table_name=table.table
                ):
                    datasets.add(ref_dataset)
        return (
            format_html(
                separator.join(
                    [
                        f'<a href="{d.get_admin_edit_url()}">{d.name}</a>'
                        for d in datasets
                    ]
                )
            )
            if datasets
            else '-'
        )

    def get_list_related_datasets(self, obj):
        return self._get_related_datasets(obj, ', ')

    get_list_related_datasets.short_description = 'Related Datasets'

    def get_detail_related_datasets(self, obj):
        return self._get_related_datasets(obj, '<br />')

    get_detail_related_datasets.short_description = 'Related Datasets'
