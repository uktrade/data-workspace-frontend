from rest_framework.pagination import CursorPagination


class CompanyFutureInterestCountriesDatasetViewCursorPagination(CursorPagination):
    """
    Cursor Pagination for CompanyFutureInterestCountries
    """

    ordering = ('id', )
