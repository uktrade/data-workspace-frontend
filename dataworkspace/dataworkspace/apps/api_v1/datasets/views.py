from django.http import HttpResponseNotFound
from rest_framework.pagination import CursorPagination
from rest_framework.views import APIView
from dataworkspace.apps.datasets.models import DataSet


class Pagination(CursorPagination):
    ordering = ('id',)
    offset_cutoff = None


class APIDatasetView(APIView):
    """
    A GET API view to return the data for the company future countries of interest dataset
    """

    def get(self, request, dataset_id, table_id):
        print('dataset_id:', dataset_id)
        print('table_id:', table_id)
        whitelist = ['future-interest-countries']
        if dataset_id in whitelist:
            # TODO: logic to get actual dataset
            dataset = DataSet.objects.values()
            paginator = Pagination()
            page = paginator.paginate_queryset(dataset, request, view=self)
            return paginator.get_paginated_response(page)
        else:
            return HttpResponseNotFound('Invalid dataset id')
