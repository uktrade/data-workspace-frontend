from dataworkspace.apps.datasets.models import DataSet
from rest_framework.pagination import CursorPagination
from rest_framework.views import APIView


class Pagination(CursorPagination):
    ordering = ('id',)
    offset_cutoff = None


class CompanyFutureInterestCountriesDatasetView(APIView):
    """
    A GET API view to return the data for the company future countries of interest dataset
    """

    def get(self, request):
        dataset = DataSet.objects.values()  # stubbed dataset
        # replace with FutureInterestCountries later
        paginator = Pagination()
        page = paginator.paginate_queryset(dataset, request, view=self)
        return paginator.get_paginated_response(page)
