class TimestampFilterMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        ts_from = self.request.query_params.get("from")
        if ts_from is not None:
            queryset = queryset.filter(timestamp__gte=ts_from)
        ts_to = self.request.query_params.get("to")
        if ts_to:
            queryset = queryset.filter(timestamp__lt=ts_to)
        return queryset
