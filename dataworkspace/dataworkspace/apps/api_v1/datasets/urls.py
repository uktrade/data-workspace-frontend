from django.urls import include, path
from dataworkspace.apps.api_v1.datasets.company_future_interest_countries.views import (
    CompanyFutureInterestCountriesDatasetView,
)

urlpatterns = [
    path(
        'future-interest-countries-dataset',
        CompanyFutureInterestCountriesDatasetView.as_view(),
        name='future-interest-countries-dataset'
    ),
]
