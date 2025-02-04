import logging

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from dataworkspace.apps.datasets.models import DataSetType, ReferenceDataset, SourceTable
from dataworkspace.apps.datasets.utils import find_dataset

from .service import DataDictionary, DataDictionaryService

logger = logging.getLogger(__name__)


def find_data_dictionary_view(request, schema_name, table_name):
    query = SourceTable.objects.filter(schema=schema_name, table=table_name)
    if query.exists():
        return redirect("datasets:data_dictionary", source_uuid=query.first().id)

    reference_dataset = get_object_or_404(ReferenceDataset, table_name=table_name)
    return redirect("datasets:data_dictionary", source_uuid=reference_dataset.uuid)


def create_dataset_view_model(dataset):
    """
    Ensures that the dataset has a UUID as the id field
    Transposes dataset.uuid -> dataset.id for reference dataset
    @param dataset: model inheriting from DataSet
    @return: The original dataset with fixed id field
    """
    if not dataset:
        return None

    if dataset.type == DataSetType.REFERENCE:
        dataset.id = dataset.uuid

    return dataset


class DataDictionaryView(View):
    def get(self, request, source_uuid):
        dataset = None

        if request.GET.get("dataset_uuid"):
            logger.info("looking for a dataset id %s", request.GET.get("dataset_uuid"))
            dataset = find_dataset(request.GET.get("dataset_uuid"), self.request.user)

        service = DataDictionaryService()
        dictionary = service.get_dictionary(source_uuid)

        return render(
            request,
            "datasets/data_dictionary.html",
            context={
                "dataset": create_dataset_view_model(dataset),
                "dictionary": dictionary,
            },
        )


class DataDictionaryEditView(View):
    def dispatch(self, request, *args, **kwargs):
        dataset_uuid = self.kwargs.get("dataset_uuid")
        dataset = find_dataset(dataset_uuid, self.request.user)
        valid_users = [
            dataset.information_asset_owner,
            dataset.information_asset_manager,
        ] + (
            list(dataset.data_catalogue_editors.all())
            if hasattr(dataset, "data_catalogue_editors")
            else []
        )
        if request.user not in valid_users and not request.user.is_superuser:
            return HttpResponseForbidden()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, dataset_uuid, source_uuid):
        logger.info("Looking for a dataset with id = %s", dataset_uuid)
        dataset = find_dataset(dataset_uuid, self.request.user)

        service = DataDictionaryService()
        dictionary = service.get_dictionary(source_uuid)

        return render(
            request,
            "datasets/manage_data_dictionary/edit_dictionary.html",
            context={
                "dataset": create_dataset_view_model(dataset),
                "dictionary": dictionary,
            },
        )

    def post(self, request, dataset_uuid, source_uuid):
        service = DataDictionaryService()

        update_rows = []
        for name, value in request.POST.items():
            if name == "csrfmiddlewaretoken":
                continue

            row = DataDictionary.DataDictionaryUpdateRow(name, value[:1024])
            update_rows.append(row)

        service.save_dictionary(source_uuid, update_rows)

        messages.success(self.request, "Changes saved successfully")
        redirect_url = (
            reverse("datasets:data_dictionary", args=[source_uuid])
            + "?dataset_uuid="
            + str(dataset_uuid)
        )
        return redirect(redirect_url)
