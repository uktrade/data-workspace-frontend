from datetime import datetime

import pytest
from pytz import UTC

from dataworkspace.apps.datasets.templatetags import datasets_tags


@pytest.mark.parametrize(
    "input_date, expected_output_date",
    [
        (datetime(2020, 1, 1, 11, 40, tzinfo=UTC), "1 January 2020, 11:40am, GMT"),
        (datetime(2020, 7, 16, 11, 40, tzinfo=UTC), "16 July 2020, 12:40pm, GMT+1"),
        (datetime(2021, 2, 17, 14, 1, tzinfo=UTC), "17 February 2021, 2:01pm, GMT"),
        (datetime(2021, 1, 1, 1, 1), "1 January 2021, 1:01am, GMT"),
    ],
)
def test_date_with_gmt_offset(input_date, expected_output_date):
    assert datasets_tags.date_with_gmt_offset(input_date) == expected_output_date
