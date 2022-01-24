import logging

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls.base import reverse_lazy
from django.views import View
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.urls import reverse
from requests import RequestException

from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.apps.datasets.pipelines.forms import PipelineCreateForm, PipelineEditForm
from dataworkspace.apps.datasets.pipelines.utils import (
    delete_pipeline_from_dataflow,
    run_pipeline,
    save_pipeline_to_dataflow,
)

logger = logging.getLogger("app")


class IsAdminMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser


class PipelineCreateView(CreateView, IsAdminMixin):
    model = Pipeline
    form_class = PipelineCreateForm
    template_name = "datasets/pipelines/pipeline_detail.html"

    def get_success_url(self):
        return reverse("pipelines:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        try:
            save_pipeline_to_dataflow(form.instance, "POST")
        except RequestException as e:
            messages.error(
                self.request, "Unable to sync pipeline to data flow. Please try saving again"
            )
            logger.exception(e)
            return self.form_invalid(form)

        messages.success(self.request, "Pipeline created successfully.")
        return super().form_valid(form)


class PipelineUpdateView(UpdateView, IsAdminMixin):
    model = Pipeline
    form_class = PipelineEditForm
    template_name = "datasets/pipelines/pipeline_detail.html"

    def get_success_url(self):
        return reverse("pipelines:index")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        try:
            save_pipeline_to_dataflow(form.instance, "PUT")
        except RequestException as e:
            messages.error(
                self.request, "Unable to sync pipeline to data flow. Please try saving again"
            )
            logger.exception(e)
            return self.form_invalid(form)

        messages.success(self.request, "Pipeline updated successfully.")
        return super().form_valid(form)


class PipelineListView(ListView, IsAdminMixin):
    model = Pipeline
    template_name = "datasets/pipelines/list.html"


class PipelineDeleteView(DeleteView, IsAdminMixin):
    model = Pipeline
    template_name = "datasets/pipelines/delete.html"
    success_url = reverse_lazy("pipelines:index")

    def delete(self, request, *args, **kwargs):
        try:
            delete_pipeline_from_dataflow(self.get_object())
        except RequestException as e:
            # If the pipeline doesn't exist on airflow, do not raise an error
            if e.response is None or e.response.status_code != 404:
                messages.error(
                    self.request,
                    "There was a problem deleting the pipeline. If the issue persists please "
                    "contact our support team.",
                )
                logger.exception(e)
                return HttpResponseRedirect(reverse("pipelines:index"))
        messages.success(self.request, "Pipeline deleted successfully.")
        return super().delete(request, *args, **kwargs)


class PipelineRunView(View, IsAdminMixin):
    model = Pipeline
    success_url = reverse_lazy("pipelines:index")

    def post(self, request, pk, *args, **kwargs):
        pipeline = get_object_or_404(Pipeline, pk=pk)
        try:
            run_pipeline(pipeline, request.user)
        except RequestException as e:
            messages.error(
                self.request,
                "There was a problem running the pipeline. If the issue persists please "
                "contact our support team.",
            )
            logger.exception(e)
        else:
            messages.success(self.request, "Pipeline triggered successfully.")
        return HttpResponseRedirect(reverse("pipelines:index"))
