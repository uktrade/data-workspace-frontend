import logging
from datetime import datetime

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import (
    AdminTextInputWidget,
    FilteredSelectMultiple,
)
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.db import transaction
from django.template.defaultfilters import filesizeformat
from django.utils.html import format_html

from dataworkspace.apps.accounts.utils import (
    SSOApiException,
    add_user_access_profile,
    remove_user_access_profile,
)
from dataworkspace.apps.core.utils import (
    stable_identification_suffix,
)
from dataworkspace.apps.datasets.constants import DataSetType, UserAccessType
from dataworkspace.apps.datasets.models import (
    DataSet,
    DataSetUserPermission,
    MasterDataset,
    DataCutDataset,
    VisualisationCatalogueItem,
    VisualisationUserPermission,
    AdminVisualisationUserPermission,
)
from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.applications.utils import (
    create_tools_access_iam_role_task,
    sync_quicksight_permissions,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_permission_change
from dataworkspace.apps.explorer.schema import clear_schema_info_cache_for_user
from dataworkspace.apps.explorer.utils import (
    remove_data_explorer_user_cached_credentials,
)
from dataworkspace.apps.your_files.models import YourFilesUserPrefixStats

logger = logging.getLogger("app")


class AppUserEditForm(forms.ModelForm):
    tools_access_role_arn = forms.CharField(
        label="Tools access IAM role arn",
        help_text="The arn for the IAM role required to start local tools",
        required=False,
        widget=AdminTextInputWidget(),
    )
    home_directory_efs_access_point_id = forms.CharField(
        label="Home directory ID",
        help_text="EFS Access Point ID",
        max_length=128,
        required=False,
        empty_value=None,
        widget=AdminTextInputWidget(),
    )
    can_start_all_applications = forms.BooleanField(
        label="Can start local tools",
        help_text="For JupyterLab, rStudio and pgAdmin",
        required=False,
    )
    can_develop_visualisations = forms.BooleanField(
        label="Can develop visualisations",
        help_text="To deploy and manage visualisations from code in Gitlab",
        required=False,
    )
    can_access_appstream = forms.BooleanField(
        label="Can access AppStream", help_text="For STATA", required=False
    )
    can_access_quicksight = forms.BooleanField(
        label="Can access QuickSight",
        help_text="Removing and reinstating Quicksight access should fix unexpected 403s for users",
        required=False,
    )
    authorized_master_datasets = forms.ModelMultipleChoiceField(
        required=False,
        widget=FilteredSelectMultiple("master datasets", False),
        queryset=MasterDataset.objects.live()
        .filter(user_access_type=UserAccessType.REQUIRES_AUTHORIZATION)
        .order_by("name"),
    )
    authorized_data_cut_datasets = forms.ModelMultipleChoiceField(
        required=False,
        widget=FilteredSelectMultiple("data cut datasets", False),
        queryset=DataCutDataset.objects.live()
        .filter(user_access_type=UserAccessType.REQUIRES_AUTHORIZATION)
        .order_by("name"),
    )
    authorized_visualisations = forms.ModelMultipleChoiceField(
        label="Authorized visualisations",
        required=False,
        widget=FilteredSelectMultiple("visualisations", False),
        queryset=None,
    )

    authorized_admin_visualisations = forms.ModelMultipleChoiceField(
        label="Authorized admin visualisations",
        required=False,
        widget=FilteredSelectMultiple("visualisations", False),
        queryset=None,
    )
    certificate_date = forms.DateField(
        label="Training completion date",
        help_text="Date that user last completed training for self-certified tool access",
        required=False,
    )
    is_renewal_email_notified = forms.BooleanField(
        label="Email renewal notification status",
        help_text="User should receieve self certify renewal email notification 30 days before expiry",
        required=False,
    )

    class Meta:
        model = get_user_model()
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs["instance"]

        self.fields["tools_access_role_arn"].initial = instance.profile.tools_access_role_arn
        self.fields["tools_access_role_arn"].widget.attrs["class"] = "vTextField"

        self.fields["home_directory_efs_access_point_id"].initial = (
            instance.profile.home_directory_efs_access_point_id
        )
        self.fields["home_directory_efs_access_point_id"].widget.attrs["class"] = "vTextField"

        self.fields["can_start_all_applications"].initial = instance.user_permissions.filter(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()

        self.fields["can_develop_visualisations"].initial = instance.user_permissions.filter(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()

        self.fields["can_access_appstream"].initial = instance.user_permissions.filter(
            codename="access_appstream",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()

        self.fields["can_access_quicksight"].initial = instance.user_permissions.filter(
            codename="access_quicksight",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        ).exists()

        self.fields["authorized_master_datasets"].initial = MasterDataset.objects.live().filter(
            datasetuserpermission__user=instance
        )
        self.fields["authorized_data_cut_datasets"].initial = DataCutDataset.objects.live().filter(
            datasetuserpermission__user=instance
        )
        self.fields[
            "authorized_visualisations"
        ].initial = VisualisationCatalogueItem.objects.live().filter(
            visualisationuserpermission__user=instance
        )
        self.fields["authorized_visualisations"].queryset = (
            VisualisationCatalogueItem.objects.live().order_by("name", "id")
        )
        self.fields[
            "authorized_admin_visualisations"
        ].initial = VisualisationCatalogueItem.objects.live().filter(
            adminvisualisationuserpermission__user=instance
        )
        self.fields["authorized_admin_visualisations"].queryset = (
            VisualisationCatalogueItem.objects.live().order_by("name", "id")
        )
        self.fields["certificate_date"].initial = instance.profile.tools_certification_date
        self.fields["is_renewal_email_notified"].initial = instance.profile.is_renewal_email_sent


admin.site.unregister(get_user_model())


class LocalToolsFilter(admin.SimpleListFilter):
    title = "Local tool access"
    parameter_name = "can_start_tools"

    def lookups(self, request, model_admin):
        return (("yes", "Can start local tools"), ("no", "Cannot start local tools"))

    def queryset(self, request, queryset):
        perm = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        if self.value() == "yes":
            return queryset.filter(user_permissions=perm)
        if self.value() == "no":
            return queryset.exclude(user_permissions=perm)
        return queryset


class AppStreamFilter(admin.SimpleListFilter):
    title = "AppStream access"
    parameter_name = "can_access_appstream"

    def lookups(self, request, model_admin):
        return (("yes", "Can access AppStream"), ("no", "Cannot access AppStream"))

    def queryset(self, request, queryset):
        perm = Permission.objects.get(
            codename="access_appstream",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        if self.value() == "yes":
            return queryset.filter(user_permissions=perm)
        if self.value() == "no":
            return queryset.exclude(user_permissions=perm)
        return queryset


class QuickSightfilter(admin.SimpleListFilter):
    title = "QuickSight access"
    parameter_name = "can_access_quicksight"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Can access AWS QuickSight"),
            ("no", "Cannot access AWS QuickSight"),
        )

    def queryset(self, request, queryset):
        perm = Permission.objects.get(
            codename="access_quicksight",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        if self.value() == "yes":
            return queryset.filter(user_permissions=perm)
        if self.value() == "no":
            return queryset.exclude(user_permissions=perm)
        return queryset


@admin.register(get_user_model())
class AppUserAdmin(UserAdmin):
    add_form_template = "admin/change_form.html"
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name")}),
    )
    list_filter = (
        "is_staff",
        "is_superuser",
        "is_active",
        "groups",
        "profile__sso_status",
        LocalToolsFilter,
        AppStreamFilter,
        QuickSightfilter,
    )
    list_display = ("email", "first_name", "last_name", "is_staff", "sso_status")

    form = AppUserEditForm
    fieldsets = [
        (
            None,
            {
                "fields": [
                    "email",
                    "sso_id",
                    "stable_id_suffix",
                    "tools_access_role_arn",
                    "home_directory_efs_access_point_id",
                    "your_files_stats",
                    "first_name",
                    "last_name",
                    "groups",
                ]
            },
        ),
        (
            "Permissions",
            {
                "fields": [
                    "can_start_all_applications",
                    "can_develop_visualisations",
                    "can_access_appstream",
                    "can_access_quicksight",
                    "is_staff",
                    "is_superuser",
                    "certificate_date",
                    "is_renewal_email_notified",
                ]
            },
        ),
        (
            "Data Access",
            {
                "fields": [
                    "authorized_master_datasets",
                    "authorized_data_cut_datasets",
                    "authorized_visualisations",
                    "authorized_admin_visualisations",
                ]
            },
        ),
    ]
    readonly_fields = ["sso_id", "stable_id_suffix", "your_files_stats"]

    def sso_status(self, obj):
        return obj.profile.get_sso_status_display()

    class Media:
        css = {"all": ("data-workspace-admin.css",)}

    def has_add_permission(self, request):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        def log_change(event_type, permission, message):
            log_permission_change(
                request.user, obj, event_type, {"permission": permission}, message
            )

        start_all_applications_permission = Permission.objects.get(
            codename="start_all_applications",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        develop_visualisations_permission = Permission.objects.get(
            codename="develop_visualisations",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        access_appstream_permission = Permission.objects.get(
            codename="access_appstream",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )
        access_quicksight_permission = Permission.objects.get(
            codename="access_quicksight",
            content_type=ContentType.objects.get_for_model(ApplicationInstance),
        )

        if "can_start_all_applications" in form.cleaned_data:
            if (
                form.cleaned_data["can_start_all_applications"]
                and start_all_applications_permission not in obj.user_permissions.all()
            ):
                obj.user_permissions.add(start_all_applications_permission)

                if not obj.profile.tools_access_role_arn:
                    create_tools_access_iam_role_task.delay(obj.id)

                log_change(
                    EventLog.TYPE_GRANTED_USER_PERMISSION,
                    "can_start_all_applications",
                    "Added can_start_all_applications permission",
                )
            elif (
                not form.cleaned_data["can_start_all_applications"]
                and start_all_applications_permission in obj.user_permissions.all()
            ):
                obj.user_permissions.remove(start_all_applications_permission)
                log_change(
                    EventLog.TYPE_REVOKED_USER_PERMISSION,
                    "can_start_all_applications",
                    "Removed can_start_all_applications permission",
                )

        if "can_develop_visualisations" in form.cleaned_data:
            if (
                form.cleaned_data["can_develop_visualisations"]
                and develop_visualisations_permission not in obj.user_permissions.all()
            ):
                obj.user_permissions.add(develop_visualisations_permission)
                log_change(
                    EventLog.TYPE_GRANTED_USER_PERMISSION,
                    "can_develop_visualisations",
                    "Added can_develop_visualisations permission",
                )
            elif (
                not form.cleaned_data["can_develop_visualisations"]
                and develop_visualisations_permission in obj.user_permissions.all()
            ):
                obj.user_permissions.remove(develop_visualisations_permission)
                log_change(
                    EventLog.TYPE_REVOKED_USER_PERMISSION,
                    "can_develop_visualisations",
                    "Removed can_develop_visualisations permission",
                )

        if "can_access_appstream" in form.cleaned_data:
            if (
                form.cleaned_data["can_access_appstream"]
                and access_appstream_permission not in obj.user_permissions.all()
            ):
                try:
                    add_user_access_profile(obj, "appstream")
                except SSOApiException as e:
                    messages.error(
                        request,
                        "Unable to give user access to appstream via SSO API: %s" % e,
                    )

                obj.user_permissions.add(access_appstream_permission)
                log_change(
                    EventLog.TYPE_GRANTED_USER_PERMISSION,
                    "can_access_appstream",
                    "Added can_access_appstream permission",
                )
            elif (
                not form.cleaned_data["can_access_appstream"]
                and access_appstream_permission in obj.user_permissions.all()
            ):
                try:
                    remove_user_access_profile(obj, "appstream")
                except SSOApiException as e:
                    messages.error(
                        request,
                        "Unable to revoke user access to appstream via SSO API: %s" % e,
                    )

                obj.user_permissions.remove(access_appstream_permission)
                log_change(
                    EventLog.TYPE_REVOKED_USER_PERMISSION,
                    "can_access_appstream",
                    "Removed can_access_appstream permission",
                )

        if "can_access_quicksight" in form.cleaned_data:
            if (
                form.cleaned_data["can_access_quicksight"]
                and access_quicksight_permission not in obj.user_permissions.all()
            ):
                try:
                    add_user_access_profile(obj, "quicksight")
                except SSOApiException as e:
                    messages.error(
                        request,
                        "Unable to give user access to quicksight via SSO API: %s" % e,
                    )

                obj.user_permissions.add(access_quicksight_permission)
                log_change(
                    EventLog.TYPE_GRANTED_USER_PERMISSION,
                    "can_access_quicksight",
                    "Added can_access_quicksight permission",
                )
            elif (
                not form.cleaned_data["can_access_quicksight"]
                and access_quicksight_permission in obj.user_permissions.all()
            ):
                try:
                    remove_user_access_profile(obj, "quicksight")
                except SSOApiException as e:
                    messages.error(
                        request,
                        "Unable to revoke user access to quicksight via SSO API: %s" % e,
                    )

                obj.user_permissions.remove(access_quicksight_permission)
                log_change(
                    EventLog.TYPE_REVOKED_USER_PERMISSION,
                    "can_access_quicksight",
                    "Removed can_access_quicksight permission",
                )

        current_datasets = set(DataSet.objects.live().filter(datasetuserpermission__user=obj))
        authorized_datasets = set(
            form.cleaned_data.get("authorized_master_datasets", DataSet.objects.none()).union(
                form.cleaned_data.get("authorized_data_cut_datasets", DataSet.objects.none())
            )
        )

        update_quicksight_permissions = False
        clear_schema_info_and_credentials_cache = False
        for dataset in authorized_datasets - current_datasets:
            DataSetUserPermission.objects.create(dataset=dataset, user=obj)
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_GRANTED_DATASET_PERMISSION,
                serializers.serialize("python", [dataset])[0],
                f"Added dataset {dataset} permission",
            )
            if dataset.type == DataSetType.MASTER:
                update_quicksight_permissions = True
            clear_schema_info_and_credentials_cache = True

        for dataset in current_datasets - authorized_datasets:
            DataSetUserPermission.objects.filter(dataset=dataset, user=obj).delete()
            log_permission_change(
                request.user,
                obj,
                EventLog.TYPE_REVOKED_DATASET_PERMISSION,
                serializers.serialize("python", [dataset])[0],
                f"Removed dataset {dataset} permission",
            )
            if dataset.type == DataSetType.MASTER:
                update_quicksight_permissions = True
            clear_schema_info_and_credentials_cache = True

        if clear_schema_info_and_credentials_cache and obj.pk:
            clear_schema_info_cache_for_user(obj)
            remove_data_explorer_user_cached_credentials(obj)

        if "authorized_visualisations" in form.cleaned_data:
            current_visualisations = VisualisationCatalogueItem.objects.filter(
                visualisationuserpermission__user=obj
            )
            for visualisation_catalogue_item in form.cleaned_data["authorized_visualisations"]:
                if visualisation_catalogue_item not in current_visualisations.all():
                    VisualisationUserPermission.objects.create(
                        visualisation=visualisation_catalogue_item, user=obj
                    )
                    log_permission_change(
                        request.user,
                        obj,
                        EventLog.TYPE_GRANTED_VISUALISATION_PERMISSION,
                        serializers.serialize("python", [visualisation_catalogue_item])[0],
                        f"Added application {visualisation_catalogue_item} permission",
                    )
            for visualisation_catalogue_item in current_visualisations:
                if (
                    visualisation_catalogue_item
                    not in form.cleaned_data["authorized_visualisations"]
                ):
                    VisualisationUserPermission.objects.filter(
                        visualisation=visualisation_catalogue_item, user=obj
                    ).delete()
                    log_permission_change(
                        request.user,
                        obj,
                        EventLog.TYPE_REVOKED_VISUALISATION_PERMISSION,
                        serializers.serialize("python", [visualisation_catalogue_item])[0],
                        f"Removed application {visualisation_catalogue_item} permission",
                    )

        if "authorized_admin_visualisations" in form.cleaned_data:
            current_visualisations = VisualisationCatalogueItem.objects.filter(
                adminvisualisationuserpermission__user=obj
            )
            for visualisation_catalogue_item in form.cleaned_data[
                "authorized_admin_visualisations"
            ]:
                if visualisation_catalogue_item not in current_visualisations.all():
                    AdminVisualisationUserPermission.objects.create(
                        visualisation=visualisation_catalogue_item, user=obj
                    )
                    log_permission_change(
                        request.user,
                        obj,
                        EventLog.TYPE_GRANTED_VISUALISATION_ADMIN_PERMISSION,
                        serializers.serialize("python", [visualisation_catalogue_item])[0],
                        f"Added application {visualisation_catalogue_item} admin permission",
                    )
            for visualisation_catalogue_item in current_visualisations:
                if (
                    visualisation_catalogue_item
                    not in form.cleaned_data["authorized_admin_visualisations"]
                ):
                    AdminVisualisationUserPermission.objects.filter(
                        visualisation=visualisation_catalogue_item, user=obj
                    ).delete()
                    log_permission_change(
                        request.user,
                        obj,
                        EventLog.TYPE_REVOKED_VISUALISATION_ADMIN_PERMISSION,
                        serializers.serialize("python", [visualisation_catalogue_item])[0],
                        f"Removed application {visualisation_catalogue_item} admin permission",
                    )

        if "home_directory_efs_access_point_id" in form.cleaned_data:
            obj.profile.home_directory_efs_access_point_id = form.cleaned_data[
                "home_directory_efs_access_point_id"
            ]

        if "tools_access_role_arn" in form.cleaned_data:
            obj.profile.tools_access_role_arn = form.cleaned_data["tools_access_role_arn"]

        if "certificate_date" in form.cleaned_data:
            obj.profile.tools_certification_date = form.cleaned_data["certificate_date"]
        if "is_renewal_email_notified" in form.cleaned_data:
            obj.profile.is_renewal_email_sent = form.cleaned_data["is_renewal_email_notified"]

        super().save_model(request, obj, form, change)

        if update_quicksight_permissions:
            sync_quicksight_permissions.delay(user_sso_ids_to_update=(str(obj.profile.sso_id),))

    def sso_id(self, instance):
        return instance.profile.sso_id

    def stable_id_suffix(self, instance):
        return stable_identification_suffix(str(instance.profile.sso_id), short=True)

    def your_files_stats(self, instance):
        try:
            latest_stats = instance.your_files_stats.latest()
        except YourFilesUserPrefixStats.DoesNotExist:
            return "N/A"

        return format_html(
            f"Total size: {filesizeformat(latest_stats.total_size_bytes)} "
            f"({latest_stats.num_files} files)<br><small>last checked: "
            f"{datetime.strftime(latest_stats.last_checked_date, '%d/%m/%Y %H:%M:%S')}</small>"
        )
