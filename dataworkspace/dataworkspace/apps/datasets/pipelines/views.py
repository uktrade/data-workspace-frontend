from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls.base import reverse_lazy
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.urls import reverse

from dataworkspace.apps.datasets.models import Pipeline
from dataworkspace.apps.datasets.pipelines.forms import PipelineCreateForm, PipelineEditForm


class PipelineCreateView(CreateView):
    model = Pipeline
    form_class = PipelineCreateForm
    template_name = "datasets/pipelines/pipeline_detail.html"

    def get_success_url(self):
        return reverse("pipelines:index")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Pipeline created successfully.")
        return super().form_valid(form)


class PipelineUpdateView(UpdateView, UserPassesTestMixin):
    model = Pipeline
    form_class = PipelineEditForm
    template_name = "datasets/pipelines/pipeline_detail.html"

    def test_func(self):
        return self.request.user.is_superuser

    def get_success_url(self):
        return reverse("pipelines:index")

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        messages.success(self.request, "Pipeline updated successfully.")
        return super().form_valid(form)


class PipelineListView(ListView, UserPassesTestMixin):
    model = Pipeline
    template_name = "datasets/pipelines/list.html"

    def test_func(self):
        return self.request.user.is_superuser


class PipelineDeleteView(DeleteView, UserPassesTestMixin):
    model = Pipeline
    template_name = "datasets/pipelines/delete.html"
    success_url = reverse_lazy("pipelines:index")

    def test_func(self):
        return self.request.user.is_superuser

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Pipeline deleted successfully.")
        return super().delete(request, *args, **kwargs)
