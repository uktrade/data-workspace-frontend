from rest_framework.pagination import CursorPagination


class TimestampCursorPagination(CursorPagination):
    ordering = ('timestamp',)
