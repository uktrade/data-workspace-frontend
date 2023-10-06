from rest_framework.pagination import CursorPagination


class CreatedDateCursorPagination(CursorPagination):
    ordering = ("created_date", "id")
    page_size_query_param = "page_size"
    max_page_size = 100
