import requests, json
import logging

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls.base import reverse_lazy
from django.views.generic import DetailView
from django.conf import settings
from django.views import View
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.urls import reverse
from requests import RequestException

from mohawk import Sender

from mohawk import Sender

from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.apps.datasets.pipelines.forms import PipelineCreateForm, PipelineEditForm
from dataworkspace.apps.datasets.pipelines.utils import (
    delete_pipeline_from_dataflow,
    list_pipelines,
    run_pipeline,
    save_pipeline_to_dataflow,
    stop_pipeline,
    get_pipeline_logs,
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

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        derived_dags = {}
        try:
            derived_dags = list_pipelines()
        except RequestException as e:
            logger.exception(e)
        for pipeline in context["object_list"]:
            pipeline.dag_details = derived_dags.get(pipeline.dag_id, None)
        return context


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


class PipelineStopView(View, IsAdminMixin):
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


class PipelineLogsDetailView(DetailView, UserPassesTestMixin):
    model = Pipeline
    template_name = "datasets/pipelines/logs.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context["log"] = get_pipeline_logs(self.object)
            messages.success(self.request, "Logs retrieved successfully.")
        except RequestException as e:
            logger.exception(e)
            messages.error(
                self.request,
                "There was a problem retrieving this pipeline's logs. If the "
                "issue persists please contact our support team.",
            )
        return context

    def test_func(self):
        return self.request.user.is_superuser





class PipelineLogsDetailView(DetailView, UserPassesTestMixin):
    model = Pipeline
    template_name = "datasets/pipelines/logs.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["log"] = self._get_api_log()
        return context

    def _get_api_log(self):
        derived_pipeline_object = self.object
        derived_pipeline_table_name = derived_pipeline_object.table_name

        # pipeline_name = "AppleCovid19MobilityTrendsPipeline"
        pipeline_name = f"DerivedPipeline-{derived_pipeline_table_name}"

        config = settings.DATAFLOW_API_CONFIG
        url = (
            f'{config["DATAFLOW_BASE_URL"]}/api/experimental/derived-dags/dag/'
            f'{pipeline_name}/logs'
        )

        hawk_creds = {
            "id": config["DATAFLOW_HAWK_ID"],
            "key": config["DATAFLOW_HAWK_KEY"],
            "algorithm": "sha256",
        }
        header = Sender(hawk_creds, url, "get", content="",
                        content_type="").request_header

        response = requests.get(url, headers={"Authorization": header,
                                              "Content-Type": ""})
        if response.status_code != 200:
            return "Error"

        try:
            json_data = response.json()
        except json.JSONDecodeError:
            return response.text

        processed_data = json_data

        return processed_data


    def test_func(self):
        return self.request.user.is_superuser


