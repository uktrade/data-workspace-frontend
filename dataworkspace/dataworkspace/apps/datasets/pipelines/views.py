import logging

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.urls.base import reverse_lazy
from django.views import View
from django.views.generic.edit import CreateView, DeleteView, FormView, UpdateView
from django.views.generic.list import ListView
from requests import RequestException

from dataworkspace.apps.core.errors import PipelineBuilderPermissionDeniedError
from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.apps.datasets.pipelines.forms import PipelineTypeForm, SQLPipelineEditForm
from dataworkspace.apps.datasets.pipelines.utils import (
    delete_pipeline_from_dataflow,
    list_pipelines,
    run_pipeline,
    save_pipeline_to_dataflow,
    stop_pipeline,
)

logger = logging.getLogger("app")


class IsAdminMixin(UserPassesTestMixin):
    def test_func(self):
        if not self.request.user.is_superuser:
            raise PipelineBuilderPermissionDeniedError()
        return True


class PipelineSelectTypeView(IsAdminMixin, FormView):
    form_class = PipelineTypeForm
    template_name = "datasets/pipelines/select_type.html"

    def form_valid(self, form):
        return HttpResponseRedirect(
            reverse(f"pipelines:create-{form.cleaned_data['pipeline_type']}")
        )


class PipelineCreateView(IsAdminMixin, CreateView):
    model = Pipeline
    template_name = "datasets/pipelines/pipeline_detail.html"

    def get_form_class(self):
        return self.kwargs["form_class"]

    def get_success_url(self):
        return reverse("pipelines:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.save(commit=False)
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


class PipelineUpdateView(IsAdminMixin, UpdateView):
    model = Pipeline
    form_class = SQLPipelineEditForm
    template_name = "datasets/pipelines/pipeline_detail.html"

    def get_form_class(self):
        return self.kwargs["form_class"]

    def get_initial(self):
        initial = super().get_initial()
        initial.update(self.get_object().config)
        return initial

    def get_success_url(self):
        return reverse("pipelines:index")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        form.save(commit=False)
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


class PipelineListView(IsAdminMixin, ListView):
    model = Pipeline
    template_name = "datasets/pipelines/list.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        if not context["object_list"].exists():
            return context

        derived_dags = {}
        try:
            derived_dags = list_pipelines()
        except RequestException as e:
            logger.exception(e)
        for pipeline in context["object_list"]:
            pipeline.dag_details = derived_dags.get(pipeline.data_flow_platform, {}).get(
                pipeline.dag_id, None
            )
        return context


class PipelineDeleteView(IsAdminMixin, DeleteView):
    model = Pipeline
    template_name = "datasets/pipelines/delete.html"

    def get_success_url(self):
        return reverse("pipelines:index")

    def post(self, request, *args, **kwargs):
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


class PipelineRunView(IsAdminMixin, View):
    model = Pipeline
    success_url = reverse_lazy("pipelines:index")

    def post(self, request, pk, *args, **kwargs):
        pipeline = get_object_or_404(Pipeline, pk=pk)
        try:
            run_pipeline(pipeline)
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


class PipelineStopView(IsAdminMixin, View):
    model = Pipeline
    success_url = reverse_lazy("pipelines:index")

    def post(self, request, pk, *args, **kwargs):
        pipeline = get_object_or_404(Pipeline, pk=pk)
        try:
            stop_pipeline(pipeline, request.user)
        except RequestException as e:
            messages.error(
                self.request,
                "There was a problem stopping the pipeline. If the issue persists please "
                "contact our support team.",
            )
            logger.exception(e)
        else:
            messages.success(self.request, "Pipeline stopped successfully.")
        return HttpResponseRedirect(reverse("pipelines:index"))
