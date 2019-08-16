import os
import boto3

from botocore.exceptions import ClientError

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import Http404, HttpResponseServerError, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView, CreateView

from dataworkspace.apps.datasets.models import ReferenceDataset, SourceLink, DataSet
from dataworkspace.apps.dw_admin.forms import ReferenceDataRowDeleteForm, clean_identifier, SourceLinkUploadForm


class ReferenceDataRecordMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser

    def _get_reference_dataset(self):
        return get_object_or_404(
            ReferenceDataset,
            pk=self.kwargs['reference_dataset_id']
        )

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        reference_dataset = self._get_reference_dataset()
        ctx.update({
            'ref_model': reference_dataset,
            'opts': reference_dataset.get_record_model_class()._meta,
            'record_id': self.kwargs.get('record_id'),
        })
        return ctx


class ReferenceDatasetAdminEditView(ReferenceDataRecordMixin, FormView):
    template_name = 'admin/reference_dataset_edit_record.html'
    object = None

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['title'] = '{} reference dataset record'.format(
            'Add' if self.kwargs.get('record_id') is None else 'Edit'
        )
        return ctx

    def get_queryset(self):
        return self._get_reference_dataset().get_records()

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        reference_dataset = self._get_reference_dataset()
        record_id = self.kwargs.get('record_id')
        kwargs['initial'] = {
            'reference_dataset': reference_dataset,
            'id': record_id
        }
        if record_id is not None:
            kwargs['instance'] = get_object_or_404(
                reference_dataset.get_record_model_class(),
                reference_dataset=reference_dataset,
                id=self.kwargs.get('record_id')
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
        field_names = ['reference_dataset'] + reference_dataset.column_names

        class DynamicReferenceDatasetRecordForm(forms.ModelForm):
            class Meta:
                model = record_model
                fields = field_names
                include = field_names
                widgets = {
                    'reference_dataset': forms.HiddenInput()
                }

            # Add the form fields/widgets
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                for field in reference_dataset.fields.all():
                    self.fields[field.column_name] = field.get_form_field()

        # Add validation for the custom identifier field
        setattr(
            DynamicReferenceDatasetRecordForm,
            'clean_{}'.format(reference_dataset.identifier_field.column_name),
            clean_identifier
        )

        return helpers.AdminForm(
            DynamicReferenceDatasetRecordForm(**self.get_form_kwargs()),
            list([(None, {'fields': field_names})]),
            {}
        )

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        reference_dataset = self._get_reference_dataset()
        try:
            reference_dataset.save_record(self.kwargs.get('record_id'), form.form.cleaned_data)
        except Exception as e:
            form.form.add_error(None, e)
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(
            self.request,
            'Reference dataset record {} successfully'.format(
                'updated' if 'record_id' in self.kwargs else 'added'
            )
        )
        instance = self._get_reference_dataset()
        return reverse('admin:datasets_referencedataset_change', args=(instance.id,))


class ReferenceDatasetAdminDeleteView(ReferenceDataRecordMixin, FormView):
    form_class = ReferenceDataRowDeleteForm
    template_name = 'admin/reference_data_delete_record.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['title'] = 'Delete Reference Data Record'
        ctx['record'] = self._get_reference_dataset().get_record_by_internal_id(
            self.kwargs.get('record_id')
        )
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        reference_dataset = self._get_reference_dataset()
        record_id = self.kwargs.get('record_id')
        record = reference_dataset.get_record_by_internal_id(record_id)
        if record is None:
            raise Http404
        kwargs.update({
            'initial': {
                'id': record_id
            }
        })
        return kwargs

    def form_valid(self, form):
        instance = self._get_reference_dataset()
        try:
            instance.delete_record(form.cleaned_data['id'])
        except Exception as e:
            form.form.add_error(None, e)
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(
            self.request,
            'Reference dataset record deleted successfully'
        )
        return reverse(
            'admin:datasets_referencedataset_change',
            args=(self._get_reference_dataset().id,)
        )


class SourceLinkUploadView(UserPassesTestMixin, CreateView):  # pylint: disable=too-many-ancestors
    model = SourceLink
    form_class = SourceLinkUploadForm
    template_name = 'admin/dataset_source_link_upload.html'
    object = None

    def test_func(self):
        return self.request.user.is_superuser

    def _get_dataset(self):
        return get_object_or_404(
            DataSet,
            pk=self.kwargs['dataset_id']
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = self._get_dataset()
        ctx.update({
            'dataset': dataset,
            'opts': dataset._meta
        })
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {
            'dataset': self._get_dataset()
        }
        return kwargs

    def get_form(self, form_class=None):
        form = self.get_form_class()(**self.get_form_kwargs())
        return helpers.AdminForm(
            form,
            list([(None, {
                'fields': [x for x in form.fields.keys()]
            })]),
            {}
        )

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.form.is_valid():
            return self.form_valid(form.form)
        return self.form_invalid(form)

    def form_valid(self, form):
        source_link = form.save(commit=False)
        source_link.link_type = SourceLink.TYPE_LOCAL
        source_link.url = os.path.join(
            's3://', 'sourcelink', str(source_link.id), form.cleaned_data['file'].name
        )
        client = boto3.client('s3')
        try:
            client.put_object(
                Body=form.cleaned_data['file'],
                Bucket=settings.AWS_UPLOADS_BUCKET,
                Key=source_link.url
            )
        except ClientError as ex:
            return HttpResponseServerError(
                'Error saving file: {}'.format(ex.response['Error']['Message'])
            )
        source_link.save()
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        messages.success(
            self.request,
            'Source link uploaded successfully'
        )
        return reverse('admin:datasets_dataset_change', args=(self._get_dataset().id,))
