from rest_framework.pagination import CursorPagination


class TimestampCursorPagination(CursorPagination):
    ordering = ("timestamp", "id")
    page_size_query_param = "page_size"
    max_page_size = 10_000
