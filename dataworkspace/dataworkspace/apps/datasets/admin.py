import csv
import functools
import logging
import uuid
from datetime import datetime

import boto3
import botocore
from adminsortable2.admin import SortableAdminBase, SortableInlineAdminMixin
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.auth import get_user_model
from django.db import transaction
from django.forms import formset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django_admin_inline_paginator.admin import TabularInlinePaginated

from dataworkspace.apps.applications.models import VisualisationTemplate
from dataworkspace.apps.applications.utils import get_data_source_id
from dataworkspace.apps.core.admin import CSPRichTextEditorMixin, DeletableTimeStampedUserAdmin
from dataworkspace.apps.datasets.constants import TagType
from dataworkspace.apps.datasets.models import (
    CustomDatasetQuery,
    DataCutDataset,
    DatasetReferenceCode,
    DataSetSubscription,
    MasterDataset,
    Pipeline,
    PipelineVersion,
    ReferenceDataset,
    ReferenceDatasetField,
    SourceLink,
    SourceTable,
    SourceTableFieldDefinition,
    SourceView,
    Tag,
    ToolQueryAuditLog,
    VisualisationCatalogueItem,
    VisualisationLink,
    VisualisationLinkSqlQuery,
)
from dataworkspace.apps.datasets.permissions.utils import (
    process_dataset_authorized_users_change,
    process_visualisation_catalogue_item_authorized_users_change,
)
from dataworkspace.apps.datasets.utils import get_dataset_table
from dataworkspace.apps.dw_admin.forms import (
    CustomDatasetQueryForm,
    CustomDatasetQueryInlineForm,
    DataCutDatasetForm,
    MasterDatasetForm,
    ReferenceDataFieldInlineForm,
    ReferenceDataInlineFormset,
    ReferenceDatasetForm,
    SourceLinkForm,
    SourceTableForm,
    SourceViewForm,
    VisualisationCatalogueItemForm,
    VisualisationLinkForm,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event

logger = logging.getLogger("app")


class DataLinkAdmin(admin.ModelAdmin):
    list_display = ("name", "format", "url", "dataset")


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
            if obj and hasattr(obj, "published"):
                return not obj.published or native_perms

            return True

        return native_perms


class SourceReferenceInlineMixin(ManageUnpublishedDatasetsMixin):
    exclude = ("reference_number",)

    def source_reference(self, instance):
        code = instance.source_reference
        if code is not None:
            return code
        return "-"


class SourceLinkInline(admin.TabularInline, SourceReferenceInlineMixin):
    template = "admin/source_link_inline.html"
    form = SourceLinkForm
    model = SourceLink
    extra = 1
    manage_unpublished_permission_codename = "datasets.manage_unpublished_datacut_datasets"


class SourceTableInline(TabularInlinePaginated, admin.TabularInline, SourceReferenceInlineMixin):
    model = SourceTable
    form = SourceTableForm
    per_page = 10
    extra = 1
    manage_unpublished_permission_codename = "datasets.manage_unpublished_master_datasets"


class SourceViewInline(admin.TabularInline, SourceReferenceInlineMixin):
    model = SourceView
    extra = 1
    manage_unpublished_permission_codename = "datasets.manage_unpublished_datacut_datasets"


class CustomDatasetQueryInline(admin.TabularInline, SourceReferenceInlineMixin):
    model = CustomDatasetQuery
    form = CustomDatasetQueryInlineForm
    extra = 0
    manage_unpublished_permission_codename = "datasets.manage_unpublished_datacut_datasets"
    readonly_fields = ("tables",)

    def tables(self, obj):
        if not obj.pk:
            return ""
        tables = obj.tables.all()
        if not tables:
            return "No tables found in query.\n\nPlease ensure the SQL is valid and that the tables exist"
        return "\n".join([f'"{t.schema}"."{t.table}"' for t in obj.tables.all()])

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)

        # SQL queries should be reviewed by a superuser
        extra_readonly = set()
        if not request.user.is_superuser and request.user.has_perm(
            self.manage_unpublished_permission_codename
        ):
            extra_readonly.add("reviewed")

        readonly_fields = readonly_fields + tuple(extra_readonly)

        return readonly_fields


class FieldDefinitionInline(admin.TabularInline):
    model = SourceTableFieldDefinition
    extra = 1
    manage_unpublished_permission_codename = "datasets.manage_unpublished_master_datasets"


def clone_dataset(modeladmin, request, queryset):
    for dataset in queryset:
        dataset.clone()


class PermissionedDatasetAdmin(DeletableTimeStampedUserAdmin, ManageUnpublishedDatasetsMixin):
    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)

        # Don't allow users who can only manage unpublished datasets, to publish a dataset
        extra_readonly = []
        if not request.user.is_superuser and request.user.has_perm(
            self.manage_unpublished_permission_codename
        ):
            extra_readonly.append("published")

        readonly_fields = readonly_fields + tuple(extra_readonly)

        return readonly_fields


class BaseDatasetAdmin(PermissionedDatasetAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = (
        "name",
        "slug",
        "short_description",
        "get_tags",
        "published",
        "number_of_downloads",
        "get_bookmarks",
        "get_average_unique_users_daily",
    )
    list_filter = ("tags",)
    search_fields = ["name"]
    actions = [clone_dataset]
    autocomplete_fields = (
        "tags",
        "enquiries_contact",
        "information_asset_owner",
        "information_asset_manager",
        "data_catalogue_editors",
    )
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "published",
                    "name",
                    "slug",
                    "tags",
                    "reference_code",
                    "short_description",
                    "description",
                    "notes",
                    "enquiries_contact",
                    "information_asset_owner",
                    "information_asset_manager",
                    "data_catalogue_editors",
                    "licence",
                    "licence_url",
                    "retention_policy",
                    "government_security_classification",
                    "sensitivity",
                    "personal_data",
                    "restrictions_on_usage",
                    "type",
                    "esda",
                ]
            },
        ),
        (
            "Permissions",
            {
                "fields": [
                    "user_access_type",
                    "eligibility_criteria",
                    "authorized_email_domains",
                    "authorized_users",
                    "request_approvers",
                ]
            },
        ),
    ]

    class Media:
        js = ("js/min/django_better_admin_arrayfield.min.js",)
        css = {
            "all": (
                "css/min/django_better_admin_arrayfield.min.css",
                "data-workspace-admin.css",
            )
        }

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context.update(
            {
                "show_save": False,
                "show_save_and_add_another": False,
            }
        )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def get_form(self, request, obj=None, **kwargs):  # pylint: disable=W0221
        form_class = super().get_form(request, obj=None, **kwargs)
        form_class.base_fields["authorized_email_domains"].widget.attrs["style"] = "width: 30em;"
        form_class.base_fields["eligibility_criteria"].widget.attrs["style"] = "width: 30em;"
        form_class.base_fields["request_approvers"].widget.attrs["style"] = "width: 30em;"
        return functools.partial(form_class, user=request.user)

    def get_tags(self, obj):
        return ", ".join([x.name for x in obj.tags.all()])

    get_tags.short_description = "Tags"

    def get_bookmarks(self, obj):
        return obj.bookmark_count()

    get_bookmarks.admin_order_field = "datasetbookmark"
    get_bookmarks.short_description = "Bookmarks"

    def get_average_unique_users_daily(self, obj):
        return f"{obj.average_unique_users_daily:.3f}"

    get_average_unique_users_daily.admin_order_field = "average_unique_users_daily"
    get_average_unique_users_daily.short_description = "Average unique daily users"

    change_form_template = "admin/custom_change_form.html"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}

        extra_context["custom_button"] = True

        return super().changeform_view(request, object_id, form_url, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        if "_save_and_view" in request.POST:
            return HttpResponseRedirect(reverse("datasets:dataset_detail", args=[obj.id]))
        elif "_continue" in request.POST:
            return super().response_add(request, obj, post_url_continue)
        else:
            return super().response_add(request, obj)

    def response_change(self, request, obj):
        if "_save_and_view" in request.POST:
            return HttpResponseRedirect(reverse("datasets:dataset_detail", args=[obj.id]))
        else:
            return super().response_change(request, obj)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        authorized_users = set(
            form.cleaned_data.get("authorized_users", get_user_model().objects.none())
        )

        added_users = (
            form.cleaned_data["data_catalogue_editors"].difference(
                obj.data_catalogue_editors.all()
            )
            if change
            else form.cleaned_data["data_catalogue_editors"]
        )

        removed_users = (
            obj.data_catalogue_editors.difference(form.cleaned_data["data_catalogue_editors"])
            if change
            else []
        )

        super().save_model(request, obj, form, change)

        process_dataset_authorized_users_change(
            authorized_users,
            request.user,
            obj,
            "user_access_type" in form.changed_data,
            "authorized_email_domains" in form.changed_data,
            isinstance(self, MasterDatasetAdmin),
        )

        for added_user in added_users:
            log_event(
                request.user,
                EventLog.TYPE_DATA_CATALOGUE_EDITOR_ADDED,
                obj,
                extra={
                    "added_user": {
                        "id": added_user.id,  # pylint: disable=no-member
                        "email": added_user.email,  # pylint: disable=no-member
                        "name": added_user.get_full_name(),  # pylint: disable=no-member
                    }
                },
            )

        for removed_user in removed_users:
            log_event(
                request.user,
                EventLog.TYPE_DATA_CATALOGUE_EDITOR_REMOVED,
                obj,
                extra={
                    "removed_user": {
                        "id": removed_user.id,  # pylint: disable=no-member
                        "email": removed_user.email,  # pylint: disable=no-member
                        "name": removed_user.get_full_name(),  # pylint: disable=no-member
                    }
                },
            )


@admin.register(MasterDataset)
class MasterDatasetAdmin(CSPRichTextEditorMixin, BaseDatasetAdmin):
    form = MasterDatasetForm
    inlines = [SourceTableInline]
    manage_unpublished_permission_codename = "datasets.manage_unpublished_master_datasets"


@admin.register(DataCutDataset)
class DataCutDatasetAdmin(CSPRichTextEditorMixin, BaseDatasetAdmin):
    form = DataCutDatasetForm
    inlines = [
        SourceLinkInline,
        SourceViewInline,
        CustomDatasetQueryInline,
    ]
    manage_unpublished_permission_codename = "datasets.manage_unpublished_datacut_datasets"

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context.update(
            {
                "show_save": False,
                "show_save_and_add_another": False,
            }
        )
        return super().render_change_form(request, context, add, change, form_url, obj)

    change_form_template = "admin/custom_change_form.html"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}

        extra_context["custom_button"] = True

        return super().changeform_view(request, object_id, form_url, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        if "_save_and_view" in request.POST:
            return HttpResponseRedirect(reverse("datasets:dataset_detail", args=[obj.id]))
        elif "_continue" in request.POST:
            return super().response_add(request, obj, post_url_continue)
        else:
            return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if "_save_and_view" in request.POST:
            return HttpResponseRedirect(reverse("datasets:dataset_detail", args=[obj.id]))
        else:
            return super().response_change(request, obj)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    fields = ["type", "name"]
    search_fields = ["name"]
    list_filter = ["type"]

    def get_search_results(self, request, queryset, search_term):
        """
        Override to allow autocomplete search to work with tag type as well as tag name
        """
        search_term = search_term.lower()
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
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
    fk_name = "reference_dataset"
    min_num = 1
    extra = 1
    exclude = ["created_date", "updated_date", "created_by", "updated_by"]
    fields = [
        "name",
        "data_type",
        "column_name",
        "relationship_name",
        "linked_reference_dataset_field",
        "description",
        "is_identifier",
        "is_display_name",
        "sort_order",
    ]
    manage_unpublished_permission_codename = "datasets.manage_unpublished_reference_datasets"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        # Do not allow a link between a reference dataset field and it's parent reference dataset
        if db_field.name == "linked_reference_dataset_field":
            parent_id = request.resolver_match.kwargs.get("object_id")
            if parent_id is not None:
                kwargs["queryset"] = ReferenceDatasetField.objects.exclude(
                    reference_dataset__id=parent_id
                ).select_related("reference_dataset")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ReferenceDataset)
class ReferenceDatasetAdmin(CSPRichTextEditorMixin, SortableAdminBase, PermissionedDatasetAdmin):
    form = ReferenceDatasetForm
    list_select_related = [
        "enquiries_contact",
        "information_asset_owner",
        "information_asset_manager",
    ]
    search_fields = (
        "name",
        "short_description",
        "table_name",
        "acronyms",
        "slug",
        "short_description",
    )
    list_per_page = 25
    change_form_template = "admin/reference_dataset_changeform.html"
    prepopulated_fields = {"slug": ("name",)}
    list_display = (
        "name",
        "slug",
        "short_description",
        "get_published_version",
        "published_at",
        "published",
        "get_bookmarks",
        "get_average_unique_users_daily",
    )
    inlines = [ReferenceDataFieldInline]
    autocomplete_fields = (
        "tags",
        "enquiries_contact",
        "information_asset_owner",
        "information_asset_manager",
    )
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "published",
                    "uuid",
                    "get_published_version",
                    "name",
                    "table_name",
                    "slug",
                    "tags",
                    "external_database",
                    "short_description",
                    "description",
                    "valid_from",
                    "valid_to",
                    "enquiries_contact",
                    "information_asset_owner",
                    "information_asset_manager",
                    "government_security_classification",
                    "sensitivity",
                    "licence",
                    "licence_url",
                    "restrictions_on_usage",
                    "sort_field",
                    "sort_direction",
                    "is_draft",
                ]
            },
        ),
    ]
    readonly_fields = ("get_published_version", "uuid")
    manage_unpublished_permission_codename = "datasets.manage_unpublished_reference_datasets"

    def get_published_version(self, obj):
        if obj.published_version == "0.0":
            return " - "
        return obj.published_version

    get_published_version.short_description = "Version"

    def get_bookmarks(self, obj):
        return obj.bookmark_count()

    get_bookmarks.admin_order_field = "referencedatasetbookmark"
    get_bookmarks.short_description = "Bookmarks"

    def get_average_unique_users_daily(self, obj):
        return f"{obj.average_unique_users_daily:.3f}"

    get_average_unique_users_daily.admin_order_field = "average_unique_users_daily"
    get_average_unique_users_daily.short_description = "Average unique daily users"

    class Media:
        js = (
            "admin/js/vendor/jquery/jquery.js",
            "admin/js/jquery.init.js",
            "data-workspace-admin.js",
            "ag-grid-community.min.js",
            "dayjs.min.js",
            "js/grid-utils.js",
            "data-grid.js",
            "purify.min.js",
            "ref-dataset-admin.js",
        )
        css = {"grid": ["ag-grid-theme.css"]}

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = super().get_readonly_fields(request, obj)

        # Do not allow editing of table names via the admin
        if obj is not None:
            return readonly_fields + ("table_name",)

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
        "name",
        "query",
        "dataset__name",
        "dataset__reference_code__code",
        "reference_number",
    ]
    form = CustomDatasetQueryForm
    exclude = ("reference_number",)
    readonly_fields = ("source_reference",)
    actions = ["export_queries"]

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)

    def export_queries(self, request, queryset):
        field_names = ["dataset_name", "query_name", "query_admin_url", "query"]
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=dataset-queries-{}.csv".format(
            datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        )
        writer = csv.DictWriter(response, field_names, quoting=csv.QUOTE_NONNUMERIC)
        writer.writeheader()
        for query in queryset:
            writer.writerow(
                {
                    "dataset_name": query.dataset.name,
                    "query_name": query.name,
                    "query_admin_url": request.build_absolute_uri(
                        reverse("admin:datasets_customdatasetquery_change", args=(query.id,))
                    ),
                    "query": query.query,
                }
            )
        return response

    export_queries.short_description = "Export Selected"


@admin.register(SourceView)
class SourceViewAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "view",
        "dataset__name",
        "dataset__reference_code__code",
        "reference_number",
    ]
    form = SourceViewForm
    exclude = ("reference_number",)
    readonly_fields = ("source_reference",)

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)


@admin.register(SourceTable)
class SourceTableAdmin(admin.ModelAdmin):
    search_fields = [
        "name",
        "table",
        "dataset__name",
        "dataset__reference_code__code",
        "reference_number",
    ]
    form = SourceTableForm
    exclude = ("reference_number",)
    readonly_fields = ("source_reference",)

    def get_queryset(self, request):
        return self.model.objects.filter(dataset__deleted=False)

    inlines = [FieldDefinitionInline]


@admin.register(VisualisationLinkSqlQuery)
class VisualisationLinkSqlQueryAdmin(admin.ModelAdmin):
    exclude = (
        "is_latest",
        "visualisation_link",
    )
    readonly_fields = ("data_set_id", "table_id", "sql_query", "view_previous_versions")
    list_display = ("id", "is_latest", "created_date")

    def get_model_perms(self, request):
        """
        Return empty perms dict thus hiding the model from admin index.
        """
        return {}

    @mark_safe
    def view_previous_versions(self, obj):
        url = reverse("admin:datasets_visualisationlinksqlquery_changelist") + (
            "?o=-3"
            f"&visualisation_link_id={obj.visualisation_link_id}"
            f"&data_set_id={obj.data_set_id}"
            f"&table_id={obj.table_id}"
        )
        return '<a href="%s">View previous versions</a>' % (url)

    view_previous_versions.allow_tags = True


class CloneDatasetForm(forms.Form):
    dataset_id = forms.CharField(disabled=True, widget=forms.HiddenInput())
    existing_dataset_name = forms.CharField(
        disabled=True, widget=forms.TextInput(attrs={"size": 80})
    )
    new_dataset_name = forms.CharField(widget=forms.TextInput(attrs={"size": 80}))
    new_data_source_owner = forms.CharField(widget=forms.TextInput(attrs={"size": 80}))


@admin.register(VisualisationLink)
class VisualisationLinkAdmin(admin.ModelAdmin):
    def get_model_perms(self, request):
        """
        Return empty perms dict thus hiding the model from admin index.
        """
        return {}

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "clone_quicksight_dataset/<uuid:dashboard_id>",
                self.admin_site.admin_view(self.handle_clone_quicksight_dataset),
            )
        ]
        return my_urls + urls

    def clone_quicksight_dataset(self, dataset_id, new_dataset_name, new_data_source_owner):
        user_region = settings.QUICKSIGHT_USER_REGION
        account_id = boto3.client("sts").get_caller_identity().get("Account")
        quicksight_client = boto3.client("quicksight")

        dataset = quicksight_client.describe_data_set(
            AwsAccountId=account_id, DataSetId=dataset_id
        )
        user = quicksight_client.describe_user(
            AwsAccountId=account_id,
            UserName=new_data_source_owner,
            Namespace=settings.QUICKSIGHT_NAMESPACE,
        )["User"]
        db_name = list(settings.DATABASES_DATA.items())[0][0]
        replacement_datasource_arn = (
            f"arn:aws:quicksight:{user_region}:{account_id}:datasource/"
            + get_data_source_id(db_name, user["Arn"])
        )

        new_physical_table_map = {}

        for mapping_id, mapping in dataset["DataSet"]["PhysicalTableMap"].items():
            new_physical_table_map[mapping_id] = mapping
            for table_id, _ in new_physical_table_map[mapping_id].items():
                new_physical_table_map[mapping_id][table_id][
                    "DataSourceArn"
                ] = replacement_datasource_arn

        quicksight_client.create_data_set(
            AwsAccountId=account_id,
            DataSetId=str(uuid.uuid4()),
            Name=new_dataset_name,
            PhysicalTableMap=new_physical_table_map,
            LogicalTableMap=dataset["DataSet"]["LogicalTableMap"],
            ImportMode=dataset["DataSet"]["ImportMode"],
            Permissions=[
                {
                    "Principal": f"arn:aws:quicksight:{user_region}:{account_id}:group/default/DataWorkspaceAdmins",
                    "Actions": [
                        "quicksight:UpdateDataSetPermissions",
                        "quicksight:DescribeDataSet",
                        "quicksight:DescribeDataSetPermissions",
                        "quicksight:PassDataSet",
                        "quicksight:DescribeIngestion",
                        "quicksight:ListIngestions",
                        "quicksight:UpdateDataSet",
                        "quicksight:DeleteDataSet",
                        "quicksight:CreateIngestion",
                        "quicksight:CancelIngestion",
                    ],
                }
            ],
        )

    def handle_clone_quicksight_dataset(self, request, dashboard_id):
        account_id = boto3.client("sts").get_caller_identity().get("Account")
        quicksight_client = boto3.client("quicksight")

        datasets_arns = quicksight_client.describe_dashboard(
            AwsAccountId=account_id, DashboardId=str(dashboard_id)
        )["Dashboard"]["Version"]["DataSetArns"]
        dataset_ids = [d[-36:] for d in datasets_arns]

        initial = []
        for dataset_id in dataset_ids:
            dataset = quicksight_client.describe_data_set(
                AwsAccountId=account_id, DataSetId=dataset_id
            )["DataSet"]
            initial.append({"dataset_id": dataset_id, "existing_dataset_name": dataset["Name"]})

        CloneDatasetFormset = formset_factory(CloneDatasetForm, extra=0)
        if request.method == "POST":
            formset = CloneDatasetFormset(request.POST, initial=initial)
            if formset.is_valid():
                for form in formset:
                    try:
                        self.clone_quicksight_dataset(
                            form.cleaned_data["dataset_id"],
                            form.cleaned_data["new_dataset_name"],
                            form.cleaned_data["new_data_source_owner"],
                        )
                        messages.success(request, "Dataset cloned successfully")
                    except botocore.exceptions.ClientError as e:
                        messages.error(request, e)
        else:
            formset = CloneDatasetFormset(initial=initial)

        context = {"formset": formset, "dashboard_id": dashboard_id}
        return TemplateResponse(request, "admin/quicksight_clone_dataset.html", context)


class VisualisationLinkInline(admin.TabularInline, ManageUnpublishedDatasetsMixin):
    form = VisualisationLinkForm
    model = VisualisationLink
    extra = 1
    manage_unpublished_permission_codename = "datasets.manage_unpublished_visualisations"
    readonly_fields = (
        "sql_queries",
        "clone_quicksight_dataset",
    )

    @mark_safe
    def sql_queries(self, obj):
        url = (
            reverse("admin:datasets_visualisationlinksqlquery_changelist")
            + f"?o=-3&visualisation_link_id={obj.id}&is_latest=True"
        )
        return '<a href="%s">View sql queries</a>' % (url)

    sql_queries.allow_tags = True

    @mark_safe
    def clone_quicksight_dataset(self, obj):
        if obj.visualisation_type != "QUICKSIGHT":
            return "-"
        url = reverse(
            "admin:datasets_visualisationlink_changelist",
        )
        return f'<a href="{url}clone_quicksight_dataset/{obj.identifier}">Clone dataset</a>'

    clone_quicksight_dataset.allow_tags = True


@admin.register(VisualisationCatalogueItem)
class VisualisationCatalogueItemAdmin(CSPRichTextEditorMixin, DeletableTimeStampedUserAdmin):
    form = VisualisationCatalogueItemForm
    list_display = (
        "name",
        "short_description",
        "published",
        "get_tags",
        "get_bookmarks",
        "get_average_unique_users_daily",
    )
    list_filter = ("tags",)
    search_fields = ["name"]
    autocomplete_fields = (
        "tags",
        "enquiries_contact",
        "information_asset_owner",
        "information_asset_manager",
        "data_catalogue_editors",
        "secondary_enquiries_contact",
    )

    fieldsets = [
        (
            None,
            {
                "fields": [
                    "published",
                    "name",
                    "slug",
                    "tags",
                    "short_description",
                    "description",
                    "enquiries_contact",
                    "secondary_enquiries_contact",
                    "information_asset_owner",
                    "information_asset_manager",
                    "data_catalogue_editors",
                    "licence",
                    "licence_url",
                    "retention_policy",
                    "government_security_classification",
                    "sensitivity",
                    "personal_data",
                    "restrictions_on_usage",
                ]
            },
        ),
        (
            "Permissions",
            {
                "fields": [
                    "user_access_type",
                    "eligibility_criteria",
                    "authorized_email_domains",
                    "authorized_users",
                    "request_approvers",
                ]
            },
        ),
        ("GitLab visualisation", {"fields": ["visualisation_template"]}),
    ]
    inlines = [VisualisationLinkInline]

    class Media:
        js = (
            "js/min/django_better_admin_arrayfield.min.js",
            "admin/js/jquery.init.js",
            "data-workspace-admin.js",
        )
        css = {
            "all": (
                "css/min/django_better_admin_arrayfield.min.css",
                "data-workspace-admin.css",
            )
        }

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context.update(
            {
                "show_save": False,
                "show_save_and_add_another": False,
            }
        )
        return super().render_change_form(request, context, add, change, form_url, obj)

    def get_form(self, request, obj=None, **kwargs):  # pylint: disable=W0221
        form_class = super().get_form(request, obj=None, **kwargs)
        form_class.base_fields["authorized_email_domains"].widget.attrs["style"] = "width: 30em;"
        form_class.base_fields["eligibility_criteria"].widget.attrs["style"] = "width: 30em;"
        form_class.base_fields["request_approvers"].widget.attrs["style"] = "width: 30em;"
        return functools.partial(form_class, user=request.user)

    def get_tags(self, obj):
        return ", ".join([x.name for x in obj.tags.all()])

    get_tags.short_description = "Tags"

    def get_bookmarks(self, obj):
        return obj.bookmark_count()

    get_bookmarks.admin_order_field = "visualisationbookmark"
    get_bookmarks.short_description = "Bookmarks"

    def get_average_unique_users_daily(self, obj):
        return f"{obj.average_unique_users_daily:.3f}"

    get_average_unique_users_daily.admin_order_field = "average_unique_users_daily"
    get_average_unique_users_daily.short_description = "Average unique daily users"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "visualisation_template":
            kwargs["queryset"] = VisualisationTemplate.objects.filter(
                application_type="VISUALISATION"
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    change_form_template = "admin/custom_change_form.html"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = extra_context or {}

        extra_context["custom_button"] = True

        return super().changeform_view(request, object_id, form_url, extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        if "_save_and_view" in request.POST:
            return HttpResponseRedirect(reverse("datasets:dataset_detail", args=[obj.id]))
        elif "_continue" in request.POST:
            return super().response_add(request, obj, post_url_continue)
        else:
            return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if "_save_and_view" in request.POST:
            return HttpResponseRedirect(reverse("datasets:dataset_detail", args=[obj.id]))
        else:
            return super().response_change(request, obj)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if obj.visualisation_template and not obj.name:
            obj.name = obj.visualisation_template.nice_name

        authorized_users = set(
            form.cleaned_data.get("authorized_users", get_user_model().objects.none())
        )

        super().save_model(request, obj, form, change)

        process_visualisation_catalogue_item_authorized_users_change(
            authorized_users,
            request.user,
            obj,
            "user_access_type" in form.changed_data,
            "authorized_email_domains" in form.changed_data,
        )


@admin.register(DatasetReferenceCode)
class DatasetReferenceCodeAdmin(admin.ModelAdmin):
    search_fields = ["code", "description"]
    fields = ["code", "description"]


@admin.register(DataSetSubscription)
class DataSetSubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "dataset",
        "user",
        "notify_on_schema_change",
        "notify_on_data_change",
        "is_active",
    ]


@admin.register(ToolQueryAuditLog)
class ToolQueryAuditLogAdmin(admin.ModelAdmin):
    search_fields = ["user__email", "rolename", "query_sql"]
    fields = [
        "id",
        "timestamp",
        "get_user_name_link",
        "user",
        "rolename",
        "database",
        "connection_from",
        "get_detail_truncated_query",
        "get_detail_related_datasets",
    ]
    list_display = [
        "timestamp",
        "get_user_email_link",
        "database",
        "rolename",
        "get_list_truncated_query",
        "get_list_related_datasets",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def _truncate_query(self, query, length):
        if len(query) > length:
            return query[:length] + "..."
        return query

    def get_list_truncated_query(self, obj):
        return self._truncate_query(
            obj.query_sql, settings.TOOL_QUERY_LOG_ADMIN_LIST_QUERY_TRUNC_LENGTH
        )

    get_list_truncated_query.short_description = "Query SQL"

    def get_detail_truncated_query(self, obj):
        return self._truncate_query(
            obj.query_sql, settings.TOOL_QUERY_LOG_ADMIN_DETAIL_QUERY_TRUNC_LENGTH
        )

    get_detail_truncated_query.short_description = "Query SQL"

    def _get_user_link(self, obj):
        return reverse("admin:auth_user_change", args=(obj.user.id,))

    def get_user_email_link(self, obj):
        return format_html(f'<a href="{self._get_user_link(obj)}">{obj.user.email}</a>')

    def get_user_name_link(self, obj):
        return format_html(f'<a href="{self._get_user_link(obj)}">{obj.user.get_full_name()}</a>')

    get_user_name_link.short_description = "User"

    def _get_related_datasets(self, obj, separator):
        datasets = get_dataset_table(obj)
        return (
            format_html(
                separator.join(
                    [f'<a href="{d.get_admin_edit_url()}">{d.name}</a>' for d in datasets]
                )
            )
            if datasets
            else "-"
        )

    def get_list_related_datasets(self, obj):
        return self._get_related_datasets(obj, ", ")

    get_list_related_datasets.short_description = "Related Datasets"

    def get_detail_related_datasets(self, obj):
        return self._get_related_datasets(obj, "<br />")

    get_detail_related_datasets.short_description = "Related Datasets"


class PipelineVersionInline(admin.TabularInline):
    model = PipelineVersion
    fields = ("table_name", "config")
    readonly_fields = ("table_name", "config")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Pipeline)
class PipelineAdmin(admin.ModelAdmin):
    list_display = ["table_name", "created_by", "created_date"]
    readonly_fields = ["created_by", "created_date", "updated_by", "modified_date"]
    inlines = (PipelineVersionInline,)
