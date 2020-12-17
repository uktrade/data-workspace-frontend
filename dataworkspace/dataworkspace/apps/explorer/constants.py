import enum


class QueryLogState(enum.Enum):
    RUNNING = 0
    FAILED = 1
    COMPLETE = 2
