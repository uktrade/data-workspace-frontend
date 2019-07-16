from django.contrib import messages
from django.contrib.admin import helpers
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import FormView

from app import models
from app.dw_admin.forms import ReferenceDataRecordEditForm, ReferenceDataRowDeleteForm


class ReferenceDataRecordMixin(UserPassesTestMixin):
    form_class = ReferenceDataRecordEditForm

    def test_func(self):
        return self.request.user.is_superuser

    def _get_instance(self):
        return get_object_or_404(
            models.ReferenceDataset,
            pk=self.kwargs['reference_dataset_id']
        )

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        instance = self._get_instance()
        ctx.update({
            'ref_model': instance,
            'opts': instance._meta,
            'record_id': self.kwargs.get('record_id'),
        })
        return ctx


class ReferenceDatasetAdminEditView(ReferenceDataRecordMixin, FormView):
    template_name = 'admin/reference_dataset_edit_record.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['title'] = '{} Reference Data Set Record'.format(
            'Add' if self.kwargs.get('record_id') is None else 'Edit'
        )
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        reference_dataset = self._get_instance()
        record = {}
        record_id = self.kwargs.get('record_id')
        if record_id is not None:
            record = reference_dataset.get_record_by_internal_id(record_id)
            if record is None:
                raise Http404
        kwargs.update({
            'record_id': record_id,
            'reference_dataset': reference_dataset,
            'initial': record,
        })
        return kwargs

    def get_form(self):
        # Standard Django forms need to be wrapped in `AdminForm`
        form = super().get_form()
        return helpers.AdminForm(
            form,
            list([(None, {'fields': form.fields})]),
            {}
        )

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        # Retrieve the actual from from the AdminForm object
        if form.form.is_valid():
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        reference_dataset = self._get_instance()
        try:
            reference_dataset.save_record(self.kwargs.get('record_id'), form.form.cleaned_data)
        except Exception as e:
            form.form.add_error(None, e)
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(
            self.request,
            'Reference data set record {} successfully'.format(
                'updated' if 'record_id' in self.kwargs else 'added'
            )
        )
        instance = self._get_instance()
        return reverse('admin:app_referencedataset_change', args=(instance.id,))


class ReferenceDatasetAdminDeleteView(ReferenceDataRecordMixin, FormView):
    form_class = ReferenceDataRowDeleteForm
    template_name = 'admin/reference_data_delete_record.html'

    def get_context_data(self, *args, **kwargs):
        ctx = super().get_context_data(*args, **kwargs)
        ctx['title'] = 'Delete Reference Data Record'
        ctx['record'] = self._get_instance().get_record_by_internal_id(self.kwargs.get('record_id'))
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        reference_dataset = self._get_instance()
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
        instance = self._get_instance()
        try:
            instance.delete_record(form.cleaned_data['id'])
        except Exception as e:
            form.form.add_error(None, e)
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        messages.success(
            self.request,
            'Reference data set record deleted successfully'
        )
        return reverse(
            'admin:app_referencedataset_change',
            args=(self._get_instance().id,)
        )
