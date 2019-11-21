from django.http import HttpResponseNotFound

# from django.shortcuts import get_object_or_404
from rest_framework.pagination import CursorPagination
from rest_framework.views import APIView
from dataworkspace.apps.datasets.models import SourceTable


class Pagination(CursorPagination):
    ordering = ('id',)
    offset_cutoff = None


class APIDatasetView(APIView):
    """
    A GET API view to return the data for the company future countries of interest dataset
    """

    def get(self, request, dataset_id, source_table_id):
        # dataset_id = '14983f3e-c557-4175-8dad-7f1a6942d949'
        # source_table_id = '5a2ee5dd-f025-4939-b0a1-bb85ab7504d7'
        whitelist = ['14983f3e-c557-4175-8dad-7f1a6942d949']
        if dataset_id in whitelist:
            # source_table = get_object_or_404(
            #     SourceTable,
            #     id=source_table_id,
            #     dataset__id=dataset_id
            # )
            paginator = Pagination()
            page = paginator.paginate_queryset(
                SourceTable.objects.values(), request, view=self
            )
            return paginator.get_paginated_response(page)
        else:
            return HttpResponseNotFound('Invalid dataset id')
