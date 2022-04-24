from dataworkspace.settings.base import *  # noqa
from dataworkspace.settings.base import INSTALLED_APPS, DEBUG

if DEBUG:
    INSTALLED_APPS += [
        "example_data",
    ]
