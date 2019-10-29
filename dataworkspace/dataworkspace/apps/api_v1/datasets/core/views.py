from rest_framework.views import APIView
from dataworkspace.apps.api_v1.datasets.core.pagination import DatasetCursorPagination

# from config.settings.types import HawkScope
# from datahub.core.auth import PaaSIPAuthentication
# from datahub.core.hawk_receiver import (
#     HawkAuthentication,
#     HawkResponseSigningMixin,
#     HawkScopePermission,
# )
# from datahub.dataset.core.pagination import DatasetCursorPagination


class BaseDatasetView(APIView):

    pagination_class = DatasetCursorPagination
    
    def get(self, request):
        """Endpoint which serves all records for a specific Dataset"""
        dataset = self.get_dataset()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(dataset, request, view=self)
        return paginator.get_paginated_response(page)

    def get_dataset(self):
        """Return a list of records"""
        raise NotImplementedError


# class BaseDatasetView(HawkResponseSigningMixin, APIView):
    # """
    # Base API view to be used for creating endpoints for consumption
    # by Data Flow and insertion into Data Workspace.
    # """

    # authentication_classes = (PaaSIPAuthentication, HawkAuthentication)
    # permission_classes = (HawkScopePermission, )
    # required_hawk_scope = HawkScope.data_flow_api
    # pagination_class = DatasetCursorPagination

    # def get(self, request):
    #     """Endpoint which serves all records for a specific Dataset"""
    #     dataset = self.get_dataset()
    #     paginator = self.pagination_class()
    #     page = paginator.paginate_queryset(dataset, request, view=self)
    #     return paginator.get_paginated_response(page)

    # def get_dataset(self):
    #     """Return a list of records"""
    #     raise NotImplementedError
        
