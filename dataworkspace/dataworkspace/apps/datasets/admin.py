import logging

from adminsortable2.admin import SortableInlineAdminMixin
from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils.encoding import force_text
from csp.decorators import csp_update

from dataworkspace.apps.applications.models import VisualisationTemplate
from dataworkspace.apps.core.admin import DeletableTimeStampedUserAdmin
from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    DataCutDataset,
    DataSetUserPermission,
    MasterDataset,
    ReferenceDataset,
    ReferenceDatasetField,
    SourceLink,
    SourceTable,
    SourceTag,
    SourceView,
    VisualisationCatalogueItem,
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
)

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


class SourceLinkInline(admin.TabularInline, ManageUnpublishedDatasetsMixin):
    template = 'admin/source_link_inline.html'
    form = SourceLinkForm
    model = SourceLink
    extra = 1
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_datacut_datasets'
    )


class SourceTableInline(admin.TabularInline, ManageUnpublishedDatasetsMixin):
    model = SourceTable
    extra = 1
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_master_datasets'
    )


class SourceViewInline(admin.TabularInline, ManageUnpublishedDatasetsMixin):
    model = SourceView
    extra = 1
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_datacut_datasets'
    )


class CustomDatasetQueryInline(admin.TabularInline, ManageUnpublishedDatasetsMixin):
    model = CustomDatasetQuery
    form = CustomDatasetQueryInlineForm
    extra = 0
    manage_unpublished_permission_codename = (
        'datasets.manage_unpublished_datacut_datasets'
    )

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
        'get_source_tags',
        'published',
        'number_of_downloads',
    )
    list_filter = ('source_tags',)
    search_fields = ['name']
    actions = [clone_dataset]
    autocomplete_fields = ['source_tags']
    fieldsets = [
        (
            None,
            {
                'fields': [
                    'published',
                    'name',
                    'slug',
                    'source_tags',
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

    def get_source_tags(self, obj):
        return ', '.join([x.name for x in obj.source_tags.all()])

    get_source_tags.short_description = 'Source Tags'

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

        user_content_type_id = ContentType.objects.get_for_model(get_user_model()).pk

        super().save_model(request, obj, form, change)

        for user in authorized_users - current_authorized_users:
            DataSetUserPermission.objects.create(dataset=obj, user=user)
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=user_content_type_id,
                object_id=user.pk,
                object_repr=force_text(user),
                action_flag=CHANGE,
                change_message=f"Added dataset {obj} permission",
            )

        for user in current_authorized_users - authorized_users:
            DataSetUserPermission.objects.filter(dataset=obj, user=user).delete()
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=user_content_type_id,
                object_id=user.pk,
                object_repr=force_text(user),
                action_flag=CHANGE,
                change_message=f"Removed dataset {obj} permission",
            )

        if original_user_access_type != obj.user_access_type:
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(obj).pk,
                object_id=obj.id,
                object_repr=force_text(obj),
                action_flag=CHANGE,
                change_message='user_access_type set to {}'.format(
                    obj.user_access_type
                ),
            )


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


@admin.register(SourceTag)
class SourceTagAdmin(admin.ModelAdmin):
    fields = ['name']
    search_fields = ['name']


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
                    'column_name',
                    'data_type',
                    'linked_reference_dataset',
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
        if db_field.name == 'linked_reference_dataset':
            parent_id = request.resolver_match.kwargs.get('object_id')
            if parent_id is not None:
                kwargs['queryset'] = ReferenceDataset.objects.exclude(id=parent_id)
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
    autocomplete_fields = ['source_tags']
    fieldsets = [
        (
            None,
            {
                'fields': [
                    'published',
                    'is_joint_dataset',
                    'get_published_version',
                    'name',
                    'table_name',
                    'slug',
                    'source_tags',
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
    search_fields = ['name', 'query', 'dataset__name']
    form = CustomDatasetQueryForm

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)


@admin.register(SourceView)
class SourceViewAdmin(admin.ModelAdmin):
    search_fields = ['name', 'view', 'dataset__name']
    form = SourceViewForm

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)


@admin.register(SourceTable)
class SourceTableAdmin(admin.ModelAdmin):
    search_fields = ['name', 'table', 'dataset__name']
    form = SourceTableForm

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)


@admin.register(VisualisationCatalogueItem)
class VisualisationCatalogueItemAdmin(
    CSPRichTextEditorMixin, DeletableTimeStampedUserAdmin
):
    list_display = ('name', 'short_description', 'published')
    search_fields = ['name']
    fieldsets = [
        (
            None,
            {
                'fields': [
                    'published',
                    'visualisation_template',
                    'slug',
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
        )
    ]

    class Media:
        js = ('js/min/django_better_admin_arrayfield.min.js', 'data-workspace-admin.js')
        css = {
            'all': (
                'css/min/django_better_admin_arrayfield.min.css',
                'data-workspace-admin.css',
            )
        }

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "visualisation_template":
            kwargs["queryset"] = VisualisationTemplate.objects.filter(
                application_type='VISUALISATION'
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        obj.name = obj.visualisation_template.nice_name

        super().save_model(request, obj, form, change)
