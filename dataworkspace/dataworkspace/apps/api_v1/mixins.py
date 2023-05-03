class TimestampSinceFilterMixin:
    def get_queryset(self):
        queryset = super().get_queryset()
        since = self.request.query_params.get("since")
        if since is not None:
            queryset = queryset.filter(timestamp__gt=since)
        return queryset
