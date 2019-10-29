from django.http import JsonResponse
from dataworkspace.apps.datasets.models import DataSet
from dataworkspace.apps.api_v1.datasets.company_future_interest_countries.pagination import \
    CompanyFutureInterestCountriesDatasetViewCursorPagination
from dataworkspace.apps.api_v1.datasets.core.views import BaseDatasetView


class CompanyFutureInterestCountriesDatasetView(BaseDatasetView):
    """
    A GET API view to return the data for the company future countries of interest dataset
    """

    pagination_class = CompanyFutureInterestCountriesDatasetViewCursorPagination
    uuid = '25086e18-aadd-4098-bc82-c80621527328'

    def get_dataset(self):
        dataset = DataSet.objects.get(id=self.uuid)
        return dataset.values()
