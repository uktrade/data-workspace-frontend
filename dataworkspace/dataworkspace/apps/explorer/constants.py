from django.db import models

CHART_BUILDER_SCHEMA = "_data_explorer_charts"


class QueryLogState(models.IntegerChoices):
    RUNNING = 0, "Running"
    FAILED = 1, "Failed"
    COMPLETE = 2, "Complete"


CHART_BUILDER_AXIS_MAP = {
    "scatter": {
        "xsrc": "xsrc",
        "ysrc": "ysrc",
    },
    "line": {
        "xsrc": "xsrc",
        "ysrc": "ysrc",
    },
    "bar": {
        "xsrc": "xsrc",
        "ysrc": "ysrc",
    },
    "pie": {
        "xsrc": "labelsrc",
        "ysrc": "valuesrc",
    },
    "scattermapbox": {
        "x": "lat",
        "y": "lon",
        "xsrc": "latsrc",
        "ysrc": "lonsrc",
    },
}
