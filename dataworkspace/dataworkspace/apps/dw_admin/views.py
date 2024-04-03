import csv
import os
from datetime import date, datetime, timedelta
from pkgutil import get_data

from botocore.exceptions import ClientError
from celery import states
from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, rrule

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.postgres.aggregates.general import BoolOr
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import (
    Avg,
    Count,
    DurationField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
    Value,
    Case,
    When,
    BooleanField,
)
from django.db.models.functions import Concat, TruncDate
from django.http import Http404, HttpResponseServerError, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import filesizeformat
from django.urls import reverse
from django.utils.timesince import timesince
from django.views.generic import FormView, CreateView, TemplateView
from django_celery_results.models import TaskResult
from psycopg2.sql import Literal, SQL, Identifier

from dataworkspace.apps.applications.models import ApplicationInstance
from dataworkspace.apps.core.boto3_client import get_s3_client
from dataworkspace.apps.datasets.models import (
    Notification,
    ReferenceDataset,
    ReferenceDatasetField,
    SourceLink,
    DataSet,
    ReferenceDatasetUploadLog,
    ReferenceDatasetUploadLogRecord,
    SourceTable,
    VisualisationCatalogueItem,
)
from dataworkspace.apps.dw_admin.forms import (
    ReferenceDataRowDeleteForm,
    ReferenceDataRowDeleteAllForm,
    SourceLinkUploadForm,
    ReferenceDataRecordUploadForm,
    clean_identifier,
)
from dataworkspace.apps.eventlog.constants import SystemStatLogEventType
from dataworkspace.apps.eventlog.models import EventLog, SystemStatLog
from dataworkspace.apps.explorer.templatetags.explorer_tags import format_duration_short
from dataworkspace.apps.your_files.models import YourFilesUserPrefixStats
from dataworkspace.datasets_db import get_all_source_tables


class SelectUserForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.all())


class CurrentOwnerAndRoleForm(SelectUserForm, forms.Form):
    role = forms.ChoiceField(
        choices=[
            ("information_asset_owner_id", "Information asset owner"),
            ("information_asset_manager_id", "Information asset manager"),
            ("enquiries_contact_id", "Enquiries contact"),
        ]
    )

    def get_user(self):
        return self.data["user"]


class SelectUserAndRoleAdminView(FormView):
    template_name = "admin/assign_dataset_ownership/select_current_user_and_role_form.html"
    form_class = CurrentOwnerAndRoleForm

    def form_valid(self, form):
        user_id = form.get_user()
        role = form.data["role"]
        return HttpResponseRedirect(
            reverse(
                "dw-admin:assign-dataset-ownership-list",
                args=(
                    user_id,
                    role,
                ),
            )
        )


class SelectDatasetAndNewUserAdminView(FormView):
    template_name = "admin/assign_dataset_ownership/select_datasets_and_new_user_form.html"
    form_class = SelectUserForm

    def get_dataset_query(self, model, db_role, current_user):
        return (
            model.objects.all()
            .annotate(
                is_owner=BoolOr(
                    Case(
                        When(
                            Q((db_role, current_user)),
                            then=True,
                        ),
                        default=False,
                        output_field=BooleanField(),
                    ),
                ),
            )
            .filter(is_owner=True)
        )

    def get_datasets(self, user_id, role):
        current_user = User.objects.all().filter(id=user_id)
        db_role = role[:-3]

        datasets = self.get_dataset_query(DataSet, db_role, current_user[0])
        ref_datasets = self.get_dataset_query(ReferenceDataset, db_role, current_user[0])
        vis_datasets = self.get_dataset_query(VisualisationCatalogueItem, db_role, current_user[0])

        return list(datasets) + list(ref_datasets) + list(vis_datasets)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def get_role_title(self, role):
        roles = {
            "information_asset_manager_id": "Information asset manager",
            "information_asset_owner_id": "Information asset owner",
            "enquiries_contact_id": "Enquiries contact",
        }
        return roles[role]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.kwargs.get("id")
        role = self.kwargs.get("role")
        context["datasets"] = self.get_datasets(user_id, role)
        context["user_id"] = User.objects.filter(id=user_id).first()
        context["role"] = self.get_role_title(role)
        return context

    def execute_sql(self, table, datasets, new_owner, role):
        with connection.cursor() as cursor:
            try:
                cursor.execute(
                    SQL(
                        "update {} set {} = {} where id in {}",
                    ).format(Identifier(table), Identifier(role), Literal(new_owner), Literal(tuple(datasets)))
                )
            except Exception as e:
                print("Error", e)

    def form_valid(self, form):
        dataset_ids = form.data.getlist("dataset_id")
        datasets = [dataset for dataset in dataset_ids if '-' in dataset]
        ref_datasets = [dataset for dataset in dataset_ids if '-' not in dataset]
        new_owner = form.data["user"]
        role = self.kwargs.get("role")

        if datasets:
            self.execute_sql('app_dataset', datasets, new_owner, role)
            self.execute_sql('datasets_visualisationcatalogueitem', datasets, new_owner, role)
        if ref_datasets:
            self.execute_sql('app_referencedataset', ref_datasets, new_owner, role)

        return HttpResponseRedirect(reverse("dw-admin:assign-dataset-ownership-confirmation"))


class ConfirmationAdminView(TemplateView):
    template_name = "admin/assign_dataset_ownership/confirmation.html"


class ReferenceDataRecordMixin(UserPassesTestMixin):
    template_name = "admin/reference_dataset_upload_records.html"

    def test_func(self):
        return self.request.user.is_superuser

    def _get_reference_dataset(self):
        return get_object_or_404(ReferenceDataset, pk=self.kwargs["reference_dataset_id"])

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        reference_dataset = self._get_reference_dataset()
        ctx.update(
            {
                "ref_model": reference_dataset,
                "opts": reference_dataset.get_record_model_class()._meta,
                "record_id": self.kwargs.get("record_id"),
            }
        )
        return ctx


class ReferenceDatasetAdminEditView(ReferenceDataRecordMixin, FormView):
    template_name = "admin/reference_dataset_edit_record.html"

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx["title"] = "{} reference dataset record".format(
            "Add" if self.kwargs.get("record_id") is None else "Edit"
        )
        return ctx

    def get_queryset(self):
        return self._get_reference_dataset().get_records()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        reference_dataset = self._get_reference_dataset()
        record_id = self.kwargs.get("record_id")
        kwargs["initial"] = {"reference_dataset": reference_dataset, "id": record_id}
        if record_id is not None:
            kwargs["instance"] = get_object_or_404(
                reference_dataset.get_record_model_class(),
                reference_dataset=reference_dataset,
                id=self.kwargs.get("record_id"),
            )
        return kwargs

    def get_form(self, form_class=None):
        """
        Dynamically create a model form based on the current state
        of the dynamically built record model class
        :param form_class:
        :return:
        """
        reference_dataset = self._get_reference_dataset()
        record_model = reference_dataset.get_record_model_class()
        field_names = ["reference_dataset"] + [
            (
                field.column_name
                if field.data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY
                else field.relationship_name
            )
            for _, field in reference_dataset.editable_fields.items()
        ]

        class DynamicReferenceDatasetRecordForm(forms.ModelForm):
            class Meta:
                model = record_model
                fields = field_names
                include = field_names
                widgets = {"reference_dataset": forms.HiddenInput()}

            # Add the form fields/widgets
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                for _, field in reference_dataset.editable_fields.items():
                    if field.data_type != ReferenceDatasetField.DATA_TYPE_FOREIGN_KEY:
                        self.fields[field.column_name] = field.get_form_field()
                    else:
                        self.fields[field.relationship_name] = field.get_form_field()

        # Add validation for the custom identifier field
        setattr(
            DynamicReferenceDatasetRecordForm,
            "clean_{}".format(reference_dataset.identifier_field.column_name),
            clean_identifier,
        )
        return helpers.AdminForm(
            DynamicReferenceDatasetRecordForm(**self.get_form_kwargs()),
            list([(None, {"fields": field_names})]),
            {},
        )

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        reference_dataset = self._get_reference_dataset()
        try:
            reference_dataset.save_record(self.kwargs.get("record_id"), form.form.cleaned_data)
        except Exception as e:  # pylint: disable=broad-except
            form.form.add_error(None, e)
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(
            self.request,
            "Reference dataset record {} successfully".format(
                "updated" if "record_id" in self.kwargs else "added"
            ),
        )
        instance = self._get_reference_dataset()
        return reverse("admin:datasets_referencedataset_change", args=(instance.id,))


class ReferenceDatasetAdminDeleteView(ReferenceDataRecordMixin, FormView):
    form_class = ReferenceDataRowDeleteForm
    template_name = "admin/reference_data_delete_record.html"

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx["title"] = "Delete Reference Data Record"
        ctx["record"] = self._get_reference_dataset().get_record_by_internal_id(
            self.kwargs.get("record_id")
        )
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        reference_dataset = self._get_reference_dataset()
        record_id = self.kwargs.get("record_id")
        record = reference_dataset.get_record_by_internal_id(record_id)
        if record is None:
            raise Http404
        kwargs.update({"reference_dataset": reference_dataset, "initial": {"id": record_id}})
        return kwargs

    def form_valid(self, form):
        instance = self._get_reference_dataset()
        try:
            instance.delete_record(form.cleaned_data["id"])
        except Exception as e:  # pylint: disable=broad-except
            form.add_error(None, e)
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Reference dataset record deleted successfully")
        return reverse(
            "admin:datasets_referencedataset_change",
            args=(self._get_reference_dataset().id,),
        )


class ReferenceDatasetAdminDeleteAllView(ReferenceDataRecordMixin, FormView):
    template_name = "admin/reference_data_delete_all_records.html"
    form_class = ReferenceDataRowDeleteAllForm

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx["reference_dataset"] = self._get_reference_dataset()
        ctx["records"] = self._get_reference_dataset().get_records()
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({"reference_dataset": self._get_reference_dataset()})
        return kwargs

    def form_valid(self, form):
        instance = self._get_reference_dataset()
        try:
            instance.delete_all_records()
        except Exception as e:  # pylint: disable=broad-except
            form.add_error(None, e)
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Reference dataset records deleted successfully")
        return reverse(
            "admin:datasets_referencedataset_change",
            args=(self._get_reference_dataset().id,),
        )


class ReferenceDatasetAdminUploadView(ReferenceDataRecordMixin, FormView):
    template_name = "admin/reference_dataset_upload_records.html"
    form_class = ReferenceDataRecordUploadForm
    upload_log = None

    def get_template_names(self):
        if self.kwargs.get("log_id") is not None:
            return "admin/reference_dataset_upload_log.html"
        return self.template_name

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        if self.kwargs.get("log_id"):
            ctx["log"] = ReferenceDatasetUploadLog.objects.get(pk=self.kwargs["log_id"])
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        reference_dataset = self._get_reference_dataset()
        kwargs.update({"reference_dataset": reference_dataset})
        return kwargs

    def form_valid(self, form):
        reader = csv.DictReader(chunk.decode("utf-8-sig") for chunk in form.cleaned_data["file"])
        reader.fieldnames = [x.lower() for x in reader.fieldnames]
        reference_dataset = self._get_reference_dataset()
        record_model_class = reference_dataset.get_record_model_class()
        field_map = {
            (
                field.name.lower()
                if field.data_type != field.DATA_TYPE_FOREIGN_KEY
                else field.relationship_name_for_record_forms.lower()
            ): field
            for _, field in reference_dataset.editable_fields.items()
        }
        self.upload_log = ReferenceDatasetUploadLog.objects.create(
            reference_dataset=reference_dataset,
            created_by=self.request.user,
            updated_by=self.request.user,
        )
        for row in reader:
            log_row = ReferenceDatasetUploadLogRecord(upload_log=self.upload_log, row_data=row)
            errors = {}
            form_data = {"reference_dataset": reference_dataset}

            for _, field in reference_dataset.editable_fields.items():
                field_name = (
                    field.name
                    if field.data_type != field.DATA_TYPE_FOREIGN_KEY
                    else field.relationship_name_for_record_forms
                )
                header_name = field_name.lower()
                value = row[header_name]
                form_field = field.get_form_field()
                if field.data_type == field_map[header_name].DATA_TYPE_FOREIGN_KEY:
                    # If the column is a "foreign key ensure the linked dataset exists
                    link_id = None
                    if value != "":
                        linked_dataset = field_map[
                            header_name
                        ].linked_reference_dataset_field.reference_dataset
                        try:
                            link_id = linked_dataset.get_record_by_custom_id(value).id
                        except linked_dataset.get_record_model_class().DoesNotExist:
                            errors[header_name] = (
                                "Identifier {} does not exist in linked dataset".format(value)
                            )
                    form_data[field.relationship_name + "_id"] = link_id
                else:
                    # Otherwise validate using the associated form field
                    try:
                        form_data[field.column_name] = form_field.clean(value)
                    except ValidationError as e:
                        errors[header_name] = str(e)

            # Fetch the existing record if it exists
            try:
                record_id = reference_dataset.get_record_by_custom_id(
                    form_data.get(reference_dataset.identifier_field.column_name)
                ).id
            except record_model_class.DoesNotExist:
                record_id = None

            if not errors:
                try:
                    reference_dataset.save_record(record_id, form_data, sync_externally=False)
                except Exception as e:  # pylint: disable=broad-except
                    log_row.status = ReferenceDatasetUploadLogRecord.STATUS_FAILURE
                    log_row.errors = [{"Error": str(e)}]
                else:
                    if record_id is not None:
                        log_row.status = ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_UPDATED
                    else:
                        log_row.status = ReferenceDatasetUploadLogRecord.STATUS_SUCCESS_ADDED
            else:
                log_row.status = ReferenceDatasetUploadLogRecord.STATUS_FAILURE
                log_row.errors = errors
            log_row.save()

        if reference_dataset.external_database is not None:
            reference_dataset.sync_to_external_database(
                reference_dataset.external_database.memorable_name
            )
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(self.request, "Reference dataset upload completed successfully")
        return reverse(
            "dw-admin:reference-dataset-record-upload-log",
            args=(self._get_reference_dataset().id, self.upload_log.id),
        )


class SourceLinkUploadView(UserPassesTestMixin, CreateView):  # pylint: disable=too-many-ancestors
    model = SourceLink
    form_class = SourceLinkUploadForm
    template_name = "admin/dataset_source_link_upload.html"

    def test_func(self):
        return self.request.user.is_superuser

    def _get_dataset(self):
        return get_object_or_404(DataSet.objects.live(), pk=self.kwargs["dataset_id"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = self._get_dataset()
        ctx.update({"dataset": dataset, "opts": dataset._meta})
        return ctx

    def get_form(self, form_class=None):
        form = self.get_form_class()(**self.get_form_kwargs())
        return helpers.AdminForm(form, list([(None, {"fields": list(form.fields.keys())})]), {})

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.form.is_valid():
            return self.form_valid(form.form)
        return self.form_invalid(form)

    def form_valid(self, form):
        source_link = form.save(commit=False)
        source_link.link_type = SourceLink.TYPE_LOCAL
        source_link.url = os.path.join(
            "s3://", "sourcelink", str(source_link.id), form.cleaned_data["file"].name
        )
        client = get_s3_client()
        try:
            client.put_object(
                Body=form.cleaned_data["file"],
                Bucket=settings.AWS_UPLOADS_BUCKET,
                Key=source_link.url,
            )
        except ClientError as ex:
            return HttpResponseServerError(
                "Error saving file: {}".format(ex.response["Error"]["Message"])
            )
        source_link.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        messages.success(self.request, "Source link uploaded successfully")
        return self._get_dataset().get_admin_edit_url()


class DataWorkspaceStatsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = "admin/data_workspace_stats.html"

    def test_func(self):
        return self.request.user.is_superuser

    def get_login_url(self):
        return reverse("admin:index")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["eventlog_model"] = EventLog
        ctx["stat_types"] = SystemStatLogEventType
        ctx["current_stats"] = []
        ctx["historic_stats"] = []
        all_tools = ApplicationInstance.objects.filter(
            application_template__application_type="TOOL",
        )
        running_tools = all_tools.filter(state="RUNNING")
        events_last_24_hours = EventLog.objects.filter(
            timestamp__gte=datetime.now() - timedelta(hours=24),
        )
        tool_instances_last_7_days = all_tools.filter(
            application_template__include_in_dw_stats=True,
            spawner_created_at__gte=datetime.now() - timedelta(days=7),
        )
        logged_tool_instances = tool_instances_last_7_days.exclude(successfully_started_at=None)

        # Currently running tools
        ctx["current_stats"].append(
            {
                "title": "Currently running tools",
                "stat": running_tools.count(),
                "subtitle": f"As of {datetime.strftime(datetime.now(), '%d/%m/%Y %H:%M')}",
                "url": f"{reverse('admin:applications_applicationinstance_changelist')}?state__exact=RUNNING",
            }
        )

        # Tools successfully started
        ctx["current_stats"].append(
            {
                "title": "Tools successfully started",
                "stat": running_tools.filter(
                    spawner_created_at__gte=datetime.now() - timedelta(hours=24),
                ).count(),
                "subtitle": "In the past 24 hours",
                "url": f"{reverse('admin:applications_applicationinstance_changelist')}?state__exact=RUNNING",
            }
        )

        # Tools failed to start
        failed_tool_events = events_last_24_hours.filter(
            event_type=EventLog.TYPE_USER_TOOL_FAILED,
        ).count()
        ctx["current_stats"].append(
            {
                "title": "Tools failed to start",
                "stat": failed_tool_events,
                "subtitle": "In the past 24 hours",
                "url": f"{reverse('admin:eventlog_eventlog_changelist')}?"
                f"event_type__exact={EventLog.TYPE_USER_TOOL_FAILED}",
                "bad_news": failed_tool_events > 0,
            }
        )

        # Oldest running tool
        if running_tools.exists():
            oldest_tool_date = running_tools.earliest("spawner_created_at").spawner_created_at
            ctx["current_stats"].append(
                {
                    "title": "Oldest running tool",
                    "stat": timesince(oldest_tool_date, depth=1),
                    "subtitle": f"Started: {datetime.strftime(oldest_tool_date, '%d/%m/%Y %H:%M')}",
                    "url": f"{reverse('admin:applications_applicationinstance_changelist')}?"
                    "?o=3&state__exact=RUNNING",
                }
            )

        # Average tool load time
        tool_start_duration = 0
        if logged_tool_instances.exists():
            tool_start_duration = (
                logged_tool_instances.annotate(
                    start_duration=ExpressionWrapper(
                        F("successfully_started_at") - F("spawner_created_at"),
                        output_field=DurationField(),
                    ),
                )
                .filter(start_duration__lt=timedelta(minutes=8))
                .aggregate(Avg("start_duration"))["start_duration__avg"]
                .total_seconds()
                * 1000
            )
        ctx["current_stats"].append(
            {
                "title": "Average tool load time",
                "stat": format_duration_short(tool_start_duration),
                "subtitle": "In the past 7 days",
                "small_text": tool_start_duration >= 3_600_000,
            }
        )

        # Data grid timeouts
        grid_timeouts = events_last_24_hours.filter(
            event_type=EventLog.TYPE_DATA_PREVIEW_TIMEOUT,
        ).count()
        ctx["current_stats"].append(
            {
                "title": "Data grid timeouts (504)",
                "stat": grid_timeouts,
                "subtitle": "In the past 24 hours",
                "bad_news": grid_timeouts > 0,
                "url": f"{reverse('admin:eventlog_eventlog_changelist')}?"
                f"event_type__exact={EventLog.TYPE_DATA_PREVIEW_TIMEOUT}",
            }
        )

        # Number of failed datacut query grid loads (from the metadata syncer)
        grid_errors = events_last_24_hours.filter(
            event_type=EventLog.TYPE_USER_DATACUT_GRID_VIEW_FAILED
        ).count()
        ctx["current_stats"].append(
            {
                "title": "Data grid query failures (500)",
                "stat": grid_errors,
                "subtitle": "In the past 24 hours",
                "bad_news": grid_errors > 0,
                "url": f"{reverse('admin:eventlog_eventlog_changelist')}?"
                f"event_type__exact={EventLog.TYPE_USER_DATACUT_GRID_VIEW_FAILED}",
            }
        )

        # Source tables that don't exist in the datasets db
        missing_source_tables = cache.get("stats_missing_source_tables")
        if missing_source_tables is None:
            try:
                missing_source_tables = (
                    SourceTable.objects.filter(dataset__published=True, dataset__deleted=False)
                    .annotate(full_table_name=Concat("schema", Value("."), "table"))
                    .exclude(full_table_name__in=get_all_source_tables())
                ).count()
            except Exception:  # pylint: disable=broad-except
                missing_source_tables = "Error!"
            else:
                cache.set(
                    "stats_missing_source_tables",
                    missing_source_tables,
                    timeout=timedelta(hours=6).total_seconds(),
                )
        ctx["current_stats"].append(
            {
                "title": "Missing source tables",
                "stat": missing_source_tables,
                "subtitle": f"{missing_source_tables } table{'s' if missing_source_tables != 1 else ''} "
                "missing from the DB",
                "bad_news": missing_source_tables > 0,
            }
        )

        # Dataset notifications sent
        ctx["current_stats"].append(
            {
                "title": "Dataset notifications sent",
                "stat": Notification.objects.filter(
                    created_date__gte=datetime.now().date()
                ).count(),
                "subtitle": "Today",
                "url": f"{reverse('admin:eventlog_eventlog_changelist')}?"
                f"event_type__exact={EventLog.TYPE_DATASET_NOTIFICATION_SENT_TO_USER}",
            }
        )

        # Average DB perms query runtime
        perms_query_runtimes = SystemStatLog.objects.filter(
            timestamp__gte=datetime.now() - timedelta(days=7),
        )
        ctx["current_stats"].append(
            {
                "title": "Average DB perms query runtime",
                "stat": (
                    f"{round(perms_query_runtimes.aggregate(Avg('stat'))['stat__avg'], 1)}s"
                    if perms_query_runtimes.exists()
                    else "N/A"
                ),
                "subtitle": "In the past 7 days",
                "url": f"{reverse('admin:eventlog_systemstatlog_changelist')}?"
                f"admin:type__exact={SystemStatLogEventType.PERMISSIONS_QUERY_RUNTIME}",
            }
        )

        # Number of failed celery tasks in the last 24 hours
        failed_tasks = TaskResult.objects.filter(
            date_done__gte=datetime.now() - timedelta(hours=24), status=states.FAILURE
        ).count()
        ctx["current_stats"].append(
            {
                "title": "Failed celery tasks",
                "stat": failed_tasks,
                "subtitle": "In the past 24 hours",
                "bad_news": failed_tasks > 0,
                "url": f"{reverse('admin:django_celery_results_taskresult_changelist')}?"
                f"status__exact=FAILURE",
            }
        )

        ctx["current_stats"].append(
            {
                "title": "S3 storage space used",
                "subtitle": "(Excludes /bigdata directory)",
                "stat": (
                    filesizeformat(
                        YourFilesUserPrefixStats.objects.filter(
                            id__in=YourFilesUserPrefixStats.objects.order_by(
                                "user_id", "-created_date"
                            )
                            .distinct("user_id")
                            .values_list("id", flat=True)
                        )
                        .values("user_id", "total_size_bytes")
                        .aggregate(Sum("total_size_bytes"))["total_size_bytes__sum"]
                    )
                ),
            }
        )

        return ctx


class DataWorkspaceTrendsView(DataWorkspaceStatsView):
    template_name = "admin/data_workspace_trends.html"
    period_map = {
        "1": "7 days",
        "2": "14 days",
        "3": "1 month",
        "4": "3 months",
        "5": "6 months",
    }
    delta_map = {
        "1": relativedelta(days=7),
        "2": relativedelta(days=14),
        "3": relativedelta(months=1),
        "4": relativedelta(months=3),
        "5": relativedelta(months=6),
    }

    def _annotate_tool_start_times(self, tool_instances, remove_abandoned):
        filters = {"start_duration__lt": timedelta(minutes=8)} if remove_abandoned else {}
        return (
            tool_instances.annotate(
                start_duration=ExpressionWrapper(
                    F("successfully_started_at") - F("spawner_created_at"),
                    output_field=DurationField(),
                ),
            )
            .filter(**filters)
            .values(date=TruncDate("successfully_started_at"))
            .annotate(Avg("start_duration"))
            .values("date", "start_duration__avg")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        period = self.request.GET.get("p", "1")
        if period not in self.period_map.keys():
            period = "1"
        ctx["period_map"] = self.period_map
        ctx["period"] = period
        ctx["period_name"] = self.period_map[period]

        rdelta = self.delta_map[period]

        today = datetime.today()

        all_tools = ApplicationInstance.objects.filter(
            application_template__include_in_dw_stats=True,
            application_template__application_type="TOOL",
            spawner_created_at__gte=today - rdelta,
        )
        all_events = EventLog.objects.filter(timestamp__gte=today - rdelta)

        timedelta_chart_data = {
            day.date(): timedelta()
            for day in rrule(
                freq=DAILY, dtstart=today - rdelta, count=(today - (today - rdelta)).days + 1
            )
        }

        integer_chart_data = {
            day.date(): 0
            for day in rrule(
                freq=DAILY, dtstart=today - rdelta, count=(today - (today - rdelta)).days + 1
            )
        }

        # Tool start time chart data
        logged_tool_instances = all_tools.exclude(successfully_started_at=None)

        # Show old stats to 27 Dec 2023
        # From 28 Dec onwards filter out tools that were abandoned while spawning
        pre_bug_tools = logged_tool_instances.filter(spawner_created_at__lte=date(2023, 12, 27))
        post_bug_tools = logged_tool_instances.filter(spawner_created_at__gt=date(2023, 12, 27))
        tool_start_times_chart_data = {
            x["date"]: x["start_duration__avg"]
            for x in self._annotate_tool_start_times(pre_bug_tools, False).union(
                self._annotate_tool_start_times(post_bug_tools, True)
            )
        }
        ctx["tool_start_time_data"] = sorted(
            {**timedelta_chart_data, **tool_start_times_chart_data}.items()
        )

        # Tools started chart
        num_tools_started_chart_data = {
            x["date"]: x["tools_started"]
            for x in logged_tool_instances.extra({"date": "date(successfully_started_at)"})
            .values("date")
            .annotate(tools_started=Count("id"))
        }
        ctx["tool_start_count_data"] = sorted(
            {**integer_chart_data, **num_tools_started_chart_data}.items()
        )

        # Tools failed chart
        num_tools_failed_chart_data = {
            x["date"]: x["tools_failed"]
            for x in all_events.filter(event_type=EventLog.TYPE_USER_TOOL_FAILED)
            .extra({"date": "date(timestamp)"})
            .values("date")
            .annotate(tools_failed=Count("timestamp__date"))
            .order_by()
        }
        ctx["tool_fail_count_data"] = sorted(
            {**integer_chart_data, **num_tools_failed_chart_data}.items()
        )

        # Grids failed to load
        num_datacuts_failed_load_data = {
            x["date"]: x["datacuts_failed"]
            for x in all_events.filter(event_type=EventLog.TYPE_USER_DATACUT_GRID_VIEW_FAILED)
            .extra({"date": "date(timestamp)"})
            .values("date")
            .annotate(datacuts_failed=Count("object_id"))
            .order_by()
        }
        ctx["grid_fail_count_data"] = sorted(
            {**integer_chart_data, **num_datacuts_failed_load_data}.items()
        )

        return ctx
