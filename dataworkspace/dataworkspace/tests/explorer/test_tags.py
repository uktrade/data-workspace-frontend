from dataworkspace.apps.explorer.templatetags.explorer_tags import (
    format_duration,
    format_duration_short,
)


def test_format_duration():
    assert format_duration(36061001.3456) == "10 hours 1 minute 1 second"
    assert format_duration(1) == "1 millisecond"
    assert format_duration(1.273) == "1.27 milliseconds"
    assert format_duration(3600000) == "1 hour 0 minutes 0 seconds"
    assert format_duration(1000.2) == "1 second 0 milliseconds"


def test_format_duration_short():
    assert format_duration_short(36061001.3456) == "10h 1m 1s"
    assert format_duration_short(1) == "1ms"
    assert format_duration_short(1.273) == "1.27ms"
    assert format_duration_short(3600000) == "1h 0m 0s"
    assert format_duration_short(1000.2) == "1s 0ms"
